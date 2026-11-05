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
        self._session_starting = False
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
        self._last_server_event = time.time()
        self._last_turn_tokens = 0

    def stop_session(self):
        """Signals the session loops to terminate."""
        if self._session_active:
            logger.info("Protocol: Stop Session Requested.")
            self._session_active = False
            # We don't clear ready_event here, let the loop handle it
            self._update_mumble_comment("Session Terminated")

    def _update_mumble_comment(self, status):
        """Updates the Mumble user comment to be SPEC-compliant."""
        try:
            avg_retries = self._total_retries / max(1, self._disconnect_count)
            reconnect_rate = f"{self._successful_reconnects}/{max(1, self._disconnect_count)}"
            
            comment = (
                f"<b>Model:</b> {self._model_id}<br/>"
                f"<b>Tokens:</b> {self._last_turn_tokens:,} / 128,000<br/>"
                f"<b>Requests:</b> {self._request_count} / 50<br/>"
                f"<hr/>"
                f"<b>Disconnections:</b> {self._disconnect_count}<br/>"
                f"<b>Avg Retries:</b> {avg_retries:.1f}<br/>"
                f"<b>Reconnect Rate:</b> {reconnect_rate}<br/>"
                f"<b>Downtime:</b> {self._disconnect_duration:.1f}s<br/>"
                f"<hr/>"
                f"<b>Status:</b> {status}"
            )
            self._mumble.users.myself.comment(comment)
        except Exception as e:
            logger.warning(f"Protocol: Could not update usage comment: {e}")

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
        logger.debug("Protocol: Uplink Task Started.")
        while self._running and self._session_active:
            try:
                msg = await asyncio.wait_for(self._send_queue.get(), timeout=0.1)
                
                if isinstance(msg, dict) and "data" in msg:
                    # RECOMMENDED: Use send_realtime_input with explicit audio Blob
                    # session.send(input=dict) uses deprecated media_chunks and causes 1007 connection abort
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=msg["data"], 
                            mime_type=msg["mime_type"]
                        )
                    )
                    
                    sent += 1

                    # Update speech time while sending to prevent internal idle timeout
                    self._last_speech_time = time.time()
                    
                    if sent % 100 == 0:
                        logger.debug(f"Protocol: Uplink Active ({sent} frames sent)")
                
                self._send_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Uplink error: {e}")
                self._session_active = False
                break
        logger.debug("Protocol: Uplink Task Stopped.")

    async def _receive_loop(self, session):
        logger.debug("Protocol: Downlink Task Started.")
        try:
            while self._running and self._session_active:
                async for message in session.receive():
                    if not self._running or not self._session_active:
                        break
                    
                    # Every server message proves the session is alive
                    self._last_server_event = time.time()

                    # Log non-content messages for deep debugging
                    if not message.server_content:
                        logger.debug(f"Protocol: Received Message -> {type(message)}")

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
                                    # Update speech time on model output to prevent idle timeout during long turns
                                    self._last_speech_time = time.time()
                                    # Log audio chunk received (sampled)
                                    if int(time.time() * 10) % 10 == 0:
                                        logger.debug(f"Protocol: Model Audio Chunk ({len(part.inline_data.data)} bytes)")
                                    await self._transport.output().write_audio(part.inline_data.data, sample_rate=24000)
                                elif part.text:
                                    logger.info(f"Protocol: Model Response -> {part.text[:100]}...")
                    
                    # 3. CONVERSATIONAL CONTINUITY
                    if message.server_content and message.server_content.turn_complete:
                        logger.debug("Protocol: Turn Complete. Maintaining Session...")
                        # Update Usage Tracking (SPEC Line 180)
                        if message.usage_metadata:
                            try:
                                p_tok = getattr(message.usage_metadata, "prompt_token_count", 0) or 0
                                c_tok = getattr(message.usage_metadata, "candidates_token_count", 0) or 0
                                self._last_turn_tokens = p_tok + c_tok
                                
                                # SPEC: Increment request count after every turn (Line 185)
                                self._request_count += 1
                            except Exception as e:
                                logger.warning(f"Protocol: Could not update usage metadata: {e}")
                        
                        self._update_mumble_comment("Interactive Lock")
                        continue

                    # Periodic status update for non-terminal messages
                    if int(time.time()) % 10 == 0:
                        self._update_mumble_comment("Interactive Lock")


                # Periodic status update for non-terminal messages
                if int(time.time()) % 10 == 0:
                    self._update_mumble_comment("Interactive Lock")
        except Exception as e:
            logger.error(f"Downlink error: {e}")

        logger.debug("Protocol: Downlink Task Stopped.")

    async def _process_input_audio(self):
        logger.info("Protocol: Input Stream Primary Consumer Active.")
        # Local buffer for pre-trigger audio (approx 1 second)
        pre_trigger_buffer = []
        # Silence keep-alive: Mumble clients transmit NOTHING while silent
        # (client-side VAD), so Gemini's server VAD never sees end-of-speech
        # and the turn never completes. Feed 100ms silence chunks whenever the
        # uplink would otherwise go dry while a session is active.
        silence_chunk = b'\x00' * 3200  # 100ms @ 16kHz mono 16-bit
        # Uplink coalescing: Gemini Live VAD does not fire on 10ms micro
        # chunks. Accumulate PCM into 100ms (3200-byte) frames before sending.
        FRAME_BYTES = 3200
        send_accum = bytearray()
        last_frame_time = time.time()
        # Wake debounce: a stray 20ms noise blip must not open a Gemini
        # session. Require ~100ms of sustained loud audio before waking.
        speech_streak = 0

        def queue_audio(data: bytes):
            send_accum.extend(data)
            while len(send_accum) >= FRAME_BYTES:
                self._send_queue.put_nowait({"data": bytes(send_accum[:FRAME_BYTES]), "mime_type": "audio/pcm;rate=16000"})
                del send_accum[:FRAME_BYTES]
        
        while self._running:
            try:
                # Try to get real audio from Mumble
                frame = await asyncio.wait_for(self._transport.input().get_audio_frame(), timeout=0.01)
                if frame:
                    last_frame_time = time.time()
                    # Log volume and update speech tracker
                    volume = audioop.rms(frame, 2)
                    
                    if volume > 100:
                        speech_streak += 1
                        # Update speech time to keep session alive
                        self._last_speech_time = time.time()
                        
                        # Stale-session watchdog: real speech is being uplinked
                        # but the server has said nothing for 10s -> the session
                        # is wedged server-side; recycle it and let the next
                        # loud frame wake a fresh one.
                        if self._session_active and speech_streak >= 5 and \
                           (time.time() - self._last_server_event) > 10:
                            logger.warning("Protocol: Stale session (speech up, server silent). Recycling.")
                            self.stop_session()
                            speech_streak = 0
                        
                        if not self._ready_event.is_set() and not self._session_active and not self._session_starting:
                            if speech_streak >= 5:  # ~100ms sustained loud audio
                                logger.info(f"Presence: Human Speech Detected ({volume}). Waking up API.")
                                self._session_starting = True
                                self._ready_event.set()
                    elif volume > 50:
                        speech_streak = 0
                        # Quiet speech still keeps session alive
                        self._last_speech_time = time.time()
                    else:
                        speech_streak = 0
                    
                    if self._session_active:
                        # Flush pre-trigger buffer on first active frame
                        if pre_trigger_buffer:
                            for f in pre_trigger_buffer:
                                queue_audio(f)
                            pre_trigger_buffer.clear()
                        
                        queue_audio(frame)
                    else:
                        # Manage pre-trigger sliding window (max 100 frames = 1s)
                        pre_trigger_buffer.append(frame)
                        if len(pre_trigger_buffer) > 100:
                            pre_trigger_buffer.pop(0)
                else:
                    raise asyncio.TimeoutError()
            except asyncio.TimeoutError:
                # Silence keep-alive (see comment above): maintain a continuous
                # 100ms-cadence stream so server VAD can close turns. The
                # synthetic silence also flushes any partial coalesced frame.
                if self._session_active and (time.time() - last_frame_time) >= 0.1:
                    queue_audio(silence_chunk)
                    last_frame_time = time.time()

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
                    end_of_speech_sensitivity="END_SENSITIVITY_HIGH"
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
                    self._session_starting = False
                    self._update_mumble_comment("Interactive Lock")
                    
                    # SPEC: Sync Mute/Deafen with Session
                    self._mumble.users.myself.unmute()
                    self._mumble.users.myself.undeafen()

                    # Run send and receive loops until one finishes or session is deactivated
                    send_task = asyncio.create_task(self._send_realtime(session))
                    recv_task = asyncio.create_task(self._receive_loop(session))
                    
                    done, pending = await asyncio.wait(
                        [send_task, recv_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Deactivate session and cancel remaining task
                    self._session_active = False
                    for task in pending:
                        task.cancel()
                        try:
                            # Use wait_for to prevent hang on cancellation
                            await asyncio.wait_for(task, timeout=1.0)
                        except (asyncio.CancelledError, asyncio.TimeoutError):
                            pass
                    
                    # Ensure both tasks are finished
                    for task in done:
                        if not task.cancelled() and task.exception():
                            logger.error(f"Session task failed: {task.exception()}")

                    logger.info("Protocol: Session Cycle Reset.")
                    await asyncio.sleep(0.1) # Stability sleep before potential immediate restart

            except Exception as e:
                logger.error(f"Protocol: Handshake Failure/Hangup: {e}")
                
                # SPEC: Dropout Stats (Lines 189-194)
                self._disconnect_count += 1
                self._last_disconnect_time = time.time()

                # Reset state for next trigger
                self._session_active = False
                self._mumble.users.myself.mute()
                
            # Always clear ready event when session ends (success or failure)
            self._ready_event.clear()
            self._session_starting = False
            
            # Update comment to show state
            if self._running:
                self._update_mumble_comment("Listening (Stealth Mode)")
            
            await asyncio.sleep(1) # Prevent rapid spin

async def main(host, port, name, channel):
    cert_file = "/bots/certs/benny.pem"
    key_file = "/bots/certs/benny_key.pem"
    mumble = pymumble_py3.Mumble(host=host, user=name, port=port, certfile=cert_file, keyfile=key_file)
    # Instantiate transport (which registers callbacks) BEFORE starting the mumble thread
    transport = MumbleTransport(mumble)
    # Enable receiving sound and then start the Mumble thread
    mumble.set_receive_sound(True)
    mumble.start()
    logger.info(f"Mumble Host: {host} (Identity: {name})")
    await transport.input().start()
    ready_event = asyncio.Event()
    
    # Shared State
    class BotState:
        def __init__(self):
            self.last_speech_time = time.time()
            self.running = True
            self.session_active = False
    
    state = BotState()

    system_instruction = (
        "You are Benny Botman. Respond VERBALLY and IMMEDIATELY. "
        "MANDATE: Explicitly state actions before taking them. "
        "Multimodal continuity is critical."
    )
    
    processor = GeminiSDKProcessor(transport, mumble, "gemini-3.8-live", system_instruction, ready_event)
    
    async def presence_manager():
        # Force initial position.
        # Doc (SYSTEM_PROMPT.md): Benny is a listener who sits in Audience.
        # The AI Test Room only exists while testers run the multi-turn
        # driver (created on demand under Hallway); in production it never
        # exists, so Benny falls back to Audience.
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

        async def test_room_watcher():
            # TEST_MODE only: the tester creates the AI Test Room on demand,
            # possibly AFTER the supervisor started this container. If the
            # room appears while we idle in Audience, join it. Production
            # never sets TEST_MODE, so this task is a no-op there.
            if not (os.environ.get("TEST_MODE") and channel == "AI Test Room"):
                return
            for _ in range(120):
                await asyncio.sleep(1)
                try:
                    myself = mumble.users.myself
                    if not myself:
                        continue
                    curr = mumble.channels[myself['channel_id']] if myself['channel_id'] in mumble.channels else None
                    if curr and "Audience" in curr.get('name', ''):
                        room = next((c for c in mumble.channels.values() if c.get('name') == "AI Test Room"), None)
                        if room:
                            logger.info("Presence: AI Test Room appeared. Joining for test run.")
                            myself.move_in(room['channel_id'])
                            return
                except Exception:
                    pass
        asyncio.create_task(test_room_watcher())
        
        # SPEC: Initial State (Muted but Undeafened = Listening)
        while mumble.is_alive() and not mumble.users.myself: await asyncio.sleep(0.5)
        if mumble.users.myself:
            mumble.users.myself.undeafen()
            mumble.users.myself.mute()
            # SPEC: Clear stale metadata
            processor._update_mumble_comment("Listening (Stealth Mode)")
            logger.info("Presence: Operational (Listening Mode).")
            logger.info(f"Presence: Current Channel={mumble.users.myself['channel_id']}, Session={mumble.users.myself['session']}")
        else:

            logger.error("Presence: Failed to connect.")
            return

        # Listening mode active via _process_input_audio
        empty_since = 0
        while mumble.is_alive():
            # SPEC: 60s Idle Timeout (Line 145)
            if state.session_active and (time.time() - state.last_speech_time) > 60:
                logger.info("Presence: 60s Idle Timeout. Terminating Session.")
                processor.stop_session()
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

            # Home recovery: if our channel vanished (temporary AI Test Room
            # deleted after a test run) murmur relocates us — observed to
            # root ("Podcast Server"), sometimes leaving a dead channel id.
            # Benny's home per the doc is Audience; root is never sanctioned,
            # so return there instead of idling among ghosts.
            try:
                myself = mumble.users.myself
                if myself and (myself['channel_id'] not in mumble.channels or myself['channel_id'] == 0):
                    aud = next((c for c in mumble.channels.values() if "Audience" in c.get('name', '')), None)
                    if aud and myself['channel_id'] != aud['channel_id']:
                        logger.info("Presence: Home recovery. Returning to Audience.")
                        myself.move_in(aud['channel_id'])
            except Exception:
                pass

            # TEST_MODE: when the tester disconnects, murmur deletes the
            # temporary AI Test Room (created by the tester) and relocates
            # whoever is inside — which also churns our connection. Leave
            # gracefully the moment the room has no humans left.
            try:
                myself = mumble.users.myself
                if myself and os.environ.get("TEST_MODE"):
                    cid = myself['channel_id']
                    curr = mumble.channels[cid] if cid in mumble.channels else None
                    if curr and curr.get('name') == "AI Test Room":
                        humans_here = [
                            u['name'] for u in mumble.users.values()
                            if u['channel_id'] == cid
                            and u['name'] not in (name, "Supervisor", "Echo")
                            and not u['name'].startswith("Recording")
                        ]
                        if not humans_here:
                            aud = next((c for c in mumble.channels.values() if "Audience" in c.get('name', '')), None)
                            if aud:
                                logger.info("Presence: Test room empty. Returning to Audience.")
                                myself.move_in(aud['channel_id'])
            except Exception:
                pass

            # Get current occupancy
            occupied = False
            humans = []
            for user in mumble.users.values():
                if not user['name'] or user['name'] in [name, "Supervisor", "Echo"] or user['name'].startswith("Recording"):
                    continue
                humans.append(user['name'])
                occupied = True


            
            # Diagnostic: Log every 10s
            if int(time.time()) % 10 == 0:
                logger.debug(f"Presence Heartbeat: Occupied={occupied}, Humans Detected={humans}")

            if occupied:
                empty_since = 0
            else:
                # If KEEP_ALIVE or TEST_MODE is set, skip auto-exit to support automated tests
                if os.environ.get("KEEP_ALIVE") or os.environ.get("TEST_MODE"):
                    if empty_since == 0:
                        empty_since = time.time()
                        logger.info("Presence: Studio area empty, but KEEP_ALIVE/TEST_MODE set - skipping exit.")
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
