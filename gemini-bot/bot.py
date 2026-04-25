import os
import asyncio
import argparse
import time
import audioop
import sys
import pymumble_py3
from loguru import logger
from google import genai
from google.genai import types

from mumble_transport import MumbleTransport

# PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python is required for compatibility
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# --- TOOLS DEFINITION ---
def list_mumble_channels(mumble):
    """Returns a list of all visible Mumble channels."""
    try:
        channels = [c['name'] for c in mumble.channels.values() if 'name' in c]
        logger.info(f"Tool Call: list_mumble_channels -> Found {len(channels)} channels.")
        return {"channels": channels}
    except Exception as e:
        return {"error": str(e)}

def move_to_channel(mumble, channel_name):
    """Moves the bot to the specified channel by name."""
    try:
        target = next((c for c in mumble.channels.values() if c.get('name') == channel_name), None)
        if target:
            mumble.users.myself.move_in(target['channel_id'])
            logger.info(f"Tool Call: move_to_channel -> Moved to '{channel_name}'")
            return {"status": "success", "channel": channel_name}
        else:
            return {"error": f"Channel '{channel_name}' not found."}
    except Exception as e:
        return {"error": str(e)}

class GeminiSDKProcessor:
    def __init__(self, transport: MumbleTransport, mumble, model_id: str, system_instruction: str, ready_event: asyncio.Event):
        self._transport = transport
        self._mumble = mumble
        self._model_id = model_id
        self._system_instruction = system_instruction
        self._ready_event = ready_event
        self._client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
            http_options={'api_version': 'v1beta'}
        )
        self._running = True
        self._session_active = False
        self._send_queue = asyncio.Queue()
        self._in_turn = False
        
        # SPEC: Usage Tracking (Lines 180-194)
        self._request_count = 0
        self._disconnect_count = 0
        self._total_retries = 0
        self._successful_reconnects = 0
        self._disconnect_duration = 0
        self._last_disconnect_time = 0
        self._last_frame_time = time.time()
        self._last_speech_time = time.time()

    async def _handle_tool_call(self, session, call):
        """Processes tool calls and sends response back to Gemini using the PERFECT SDK pattern."""
        logger.info(f"Protocol: Tool CALL -> {call.name}")
        if call.name == "list_mumble_channels":
            result = list_mumble_channels(self._mumble)
        elif call.name == "move_to_channel":
            result = move_to_channel(self._mumble, call.args.get("channel_name"))
        else:
            result = {"error": "Unknown tool"}

        # DEFINITIVE v1beta Tool Response Pattern
        response = types.FunctionResponse(
            name=call.name,
            id=call.id,
            response={"result": result}
        )
        await session.send_tool_response(function_responses=[response])

    async def _send_realtime(self, session):
        sent = 0
        while self._running and self._session_active:
            try:
                msg = await asyncio.wait_for(self._send_queue.get(), timeout=0.1)
                
                if isinstance(msg, dict) and "audio" in msg:
                    # DEFINITIVE v1beta Audio Pattern
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=msg["audio"]["data"], 
                            mime_type=msg["audio"]["mime_type"]
                        )
                    )
                    sent += 1
                    if sent % 100 == 0:
                        pass
                
                self._send_queue.task_done()
            except asyncio.TimeoutError: continue
            except Exception as e:
                logger.error(f"Uplink error: {e}")
                self._session_active = False
                break

    async def _receive_loop(self, session):
        async for message in session.receive():
            if not self._running or not self._session_active: break
            
            # 1. Handle Tool Calls
            if message.tool_call:
                for call in message.tool_call.function_calls:
                    await self._handle_tool_call(session, call)

            # 2. Handle Audio Output
            if message.server_content:
                # Handle Interruption: Clear buffer immediately
                if message.server_content.interrupted:
                    logger.debug("Protocol: Interrupt Signal -> Clearing Output Buffer.")
                    self._mumble.sound_output.clear_buffer()

                # Process Model Turn Parts
                if message.server_content.model_turn:
                    parts = message.server_content.model_turn.parts
                    for part in parts:
                        if part.inline_data:
                            await self._transport.output().write_audio(part.inline_data.data, sample_rate=24000)
                        elif part.text:
                            logger.info(f"Protocol: Model Response -> {part.text[:100]}...")
            
            # 3. CONVERSATIONAL CONTINUITY: **Protocol (Single-Session)**: **NEVER RESET THE SESSION**.
            if message.server_content and message.server_content.turn_complete:
                logger.debug("Protocol: Turn Complete. Maintaining Session...")
                
                # Update Usage Tracking (SPEC Line 180)
                if message.usage_metadata:
                    try:
                        p_tok = getattr(message.usage_metadata, "prompt_token_count", 0) or 0
                        c_tok = getattr(message.usage_metadata, "candidates_token_count", 0) or 0
                        t_tok = p_tok + c_tok
                        
                        # SPEC: Increment request count after every turn (Line 185)
                        self._request_count += 1
                        
                        # SPEC: Dropout Stats (Lines 189-194)
                        avg_retries = self._total_retries / max(1, self._disconnect_count)
                        reconnect_rate = f"{self._successful_reconnects}/{max(1, self._disconnect_count)}"
                        
                        comment = (
                            f"<b>Model:</b> {self._model_id}<br/>"
                            f"<b>Tokens:</b> {t_tok:,} / 128,000<br/>"
                            f"<b>Requests:</b> {self._request_count} / 50<br/>"
                            f"<hr/>"
                            f"<b>Disconnections:</b> {self._disconnect_count}<br/>"
                            f"<b>Avg Retries:</b> {avg_retries:.1f}<br/>"
                            f"<b>Reconnect Rate:</b> {reconnect_rate}<br/>"
                            f"<b>Downtime:</b> {self._disconnect_duration:.1f}s<br/>"
                            f"<hr/>"
                            f"<b>Status:</b> Interactive Lock"
                        )
                        self._mumble.users.myself.comment(comment)
                    except Exception as e:
                        logger.warning(f"Protocol: Could not update usage comment: {e}")
                continue

    async def _process_input_audio(self):
        logger.info("Protocol: Input Stream Primary Consumer Active.")
        
        # 16kHz Mono (2 bytes per sample) -> 10ms = 160 samples = 320 bytes
        silence_frame = b'\x00' * 320
        
        while self._running:
            try:
                # Try to get real audio from Mumble
                frame = await asyncio.wait_for(self._transport.input().get_audio_frame(), timeout=0.01)
                if frame:
                    # Log volume and update speech tracker
                    volume = audioop.rms(frame, 2)
                    if volume > 200:
                        self._last_speech_time = time.time()
                        if not self._ready_event.is_set() and not self._session_active:
                            logger.info(f"Presence: Human Speech Detected ({volume}). Waking up API.")
                            self._mumble.users.myself.unmute()
                            self._mumble.users.myself.undeafen()
                            self._ready_event.set()
                    if volume > 10: 
                        pass
                         
                    # Only send to API if session is actually active
                    if self._session_active:
                        self._send_queue.put_nowait({"audio": {"data": frame, "mime_type": "audio/pcm"}})
                else:
                    raise asyncio.TimeoutError()
            except asyncio.TimeoutError:
                pass  # Do not flood the websocket with silence frames; let VAD handle pauses naturally
            except Exception as e:
                logger.error(f"Input error: {e}")
                self._running = False
                break

    async def _sdk_loop(self):
        # ... tools definition ...
        tools = [types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="list_mumble_channels",
                    description="List all channels names in the server",
                    parameters=None
                ),
                types.FunctionDeclaration(
                    name="move_to_channel",
                    description="Move the bot to a specific channel room",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "channel_name": types.Schema(type="STRING", description="Target channel name")
                        },
                        required=["channel_name"]
                    )
                )
            ]
        )]
        
        config = types.LiveConnectConfig(
            system_instruction=self._system_instruction,
            tools=tools,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Fenrir"))
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity="START_SENSITIVITY_LOW",
                    end_of_speech_sensitivity="END_SENSITIVITY_LOW"
                )
            ),
            response_modalities=["AUDIO"]
        )

        while self._running:
            # SPEC: Wait for Human Trigger
            await self._ready_event.wait()
            
            logger.info(f"Protocol: Handshake Initiated (Model: {self._model_id})")
            try:
                async with self._client.aio.live.connect(
                    model=self._model_id,
                    config=config
                ) as session:
                    # SPEC: Dropout Stats (Lines 189-194)
                    if self._last_disconnect_time > 0:
                        duration = time.time() - self._last_disconnect_time
                        self._disconnect_duration += duration
                        self._successful_reconnects += 1
                        self._last_disconnect_time = 0
                        logger.info(f"Protocol: Reconnected. Total Downtime: {self._disconnect_duration:.1f}s")

                    logger.info("Protocol: Session READY (Interactive Lock Achieved).")
                    self._session_active = True
                    
                    # SPEC: Sync Mute/Deafen with Session
                    self._mumble.users.myself.unmute()
                    self._mumble.users.myself.undeafen()
                    
                    await asyncio.gather(
                        self._send_realtime(session),
                        self._receive_loop(session)
                    )
                    logger.info("Protocol: Session Cycle Reset.")
            except Exception as e:
                logger.error(f"Protocol: Handshake Failure/Hangup: {e}")
                
                # SPEC: Dropout Stats (Lines 189-194)
                self._disconnect_count += 1
                self._last_disconnect_time = time.time()
                
                # Reset state for next trigger
                self._session_active = False
                self._mumble.users.myself.mute()
                self._ready_event.clear()
                
                # Update comment immediately to show Offline status if possible
                try:
                    self._mumble.users.myself.comment(f"<b>Model:</b> {self._model_id}<br/><b>Status:</b> 🔴 Disconnected")
                except: pass
                
                await asyncio.sleep(2) # Prevent rapid spin

async def main(host, port, name, channel):
    cert_file = "/bots/certs/benny.pem"
    key_file = "/bots/certs/benny_key.pem"
    mumble = pymumble_py3.Mumble(host=host, user=name, port=port, certfile=cert_file, keyfile=key_file)
    mumble.set_receive_sound(True)
    mumble.start()
    logger.info(f"Mumble Host: {host} (Identity: {name})")
    
    transport = MumbleTransport(mumble)
    await transport.input().start()
    ready_event = asyncio.Event()
    
    # Shared State
    class BotState:
        def __init__(self):
            self.last_speech_time = time.time()
            self.running = True
            self.session_active = False
    
    state = BotState()
    
    async def presence_manager():
        # Force initial position
        target_channel = channel
        while mumble.is_alive():
            try:
                ch = next((c for c in mumble.channels.values() if c.get('name') == target_channel), None)
                if not ch:
                    if target_channel == "AI Test Room":
                        target_channel = "Audience 👂"
                        continue
                else:
                    mumble.users.myself.move_in(ch['channel_id'])
                    break
            except Exception: pass
            await asyncio.sleep(1)
        
        # SPEC: Initial State (Muted but Undeafened = Listening)
        while mumble.is_alive() and not mumble.users.myself: await asyncio.sleep(0.5)
        if mumble.users.myself:
            mumble.users.myself.undeafen()
            mumble.users.myself.mute()
            
            # SPEC: Clear stale metadata
            initial_comment = (
                f"<b>Model:</b> gemini-3.1-flash-live-preview<br/>"
                f"<b>Status:</b> Listening (Stealth Mode)"
            )
            mumble.users.myself.comment(initial_comment)
            logger.info("Presence: Operational (Listening Mode).")
        else:
            logger.error("Presence: Failed to connect.")
            return
        
        # Listening mode active via _process_input_audio
        empty_since = 0
        while mumble.is_alive():
            # SPEC: 60s Idle Timeout (Line 145)
            if state.session_active and (time.time() - state.last_speech_time) > 60:
                logger.info("Presence: 60s Idle Timeout. Terminating Session.")
                ready_event.clear()
                state.session_active = False 
                
                # SPEC: Move back to Audience if on stage
                myself = mumble.users.myself
                curr_ch = mumble.channels.get(myself['channel_id'])
                if curr_ch and "Stage" in curr_ch['name']:
                    aud = next((c for c in mumble.channels.values() if "Audience" in c.get('name', '')), None)
                    if aud:
                        logger.info("Presence: Moving Stage -> Audience.")
                        myself.move_in(aud['channel_id'])

            # Get current occupancy
            occupied = False
            humans = []
            for user in mumble.users.values():
                if not user['name'] or user['name'] in [name, "Supervisor", "Echo"] or user['name'].startswith("Recording"):
                    continue
                humans.append(user['name'])
                chan_id = user['channel_id']
                chan = mumble.channels.get(chan_id)
                if chan:
                    cname = chan.get('name', '')
                    if any(x in cname for x in ["Studio", "Stage", "Audience", "Hallway"]):
                        occupied = True
                        break
            
            # Diagnostic: Log every 10s
            if int(time.time()) % 10 == 0:
                logger.debug(f"Presence Heartbeat: Occupied={occupied}, Humans Detected={humans}")

            if occupied:
                empty_since = 0
            else:
                if empty_since == 0:
                    empty_since = time.time()
                    logger.info("Presence: Studio area empty. Starting 30s exit timer.")
                elif time.time() - empty_since > 30:
                    logger.info("Presence: Exit timer expired. Leaving server.")
                    mumble.stop()
                    sys.exit(0)
            
            await asyncio.sleep(1.0)
            
        logger.error("Presence: Connection lost or kicked. Forcing restart.")
        os._exit(1)

    system_instruction = (
        "You are Benny Botman. Respond VERBALLY and IMMEDIATELY. "
        "MANDATE: Explicitly state actions before taking them. "
        "Multimodal continuity is critical."
    )
    
    processor = GeminiSDKProcessor(transport, mumble, "gemini-3.1-flash-live-preview", system_instruction, ready_event)
    
    async def state_linker():
        while mumble.is_alive():
            state.last_speech_time = processor._last_speech_time
            state.session_active = processor._session_active
            await asyncio.sleep(0.1)

    await asyncio.gather(
        presence_manager(),
        processor._sdk_loop(),
        processor._process_input_audio(),
        state_linker()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="murmur")
    parser.add_argument("--port", type=int, default=64738)
    parser.add_argument("--name", default="Benny Botman")
    parser.add_argument("--channel", default="AI Test Room")
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.host, args.port, args.name, args.channel))
    except (KeyboardInterrupt, SystemExit):
        pass
