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
        self._last_frame_time = time.time()
        self._in_turn = False

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
        
        # Maintain Turn Stability with Phonetic Heartbeat
        await session.send_realtime_input(
            audio=types.Blob(data=b'\x00' * 3200, mime_type="audio/pcm")
        )

    async def _send_realtime(self, session):
        while self._running and self._session_active:
            try:
                msg = await asyncio.wait_for(self._send_queue.get(), timeout=0.1)
                
                if isinstance(msg, dict):
                    if "audio" in msg:
                        # DEFINITIVE v1beta Audio Pattern
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=msg["audio"]["data"], 
                                mime_type=msg["audio"]["mime_type"]
                            )
                        )
                    elif "audio_stream_end" in msg:
                        # DEFINITIVE v1beta Turn Switch Pattern
                        await session.send_realtime_input(audio_stream_end=True)
                
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
            if message.server_content and message.server_content.model_turn:
                parts = message.server_content.model_turn.parts
                for part in parts:
                    if part.inline_data:
                        await self._transport.output().write_audio(part.inline_data.data, sample_rate=24000)
            
            # 3. CONVERSATIONAL CONTINUITY: **Protocol (Single-Session)**: **NEVER RESET THE SESSION**. The Gemini Live API maintains conversational context within a single WebSocket connection. Resetting the session on `turn_complete` causes amnesia and voice inconsistency.
            if message.server_content and message.server_content.turn_complete:
                logger.info("Protocol: Turn Complete. Maintaining Session...")
                continue

    async def _process_input_audio(self):
        await self._ready_event.wait()
        logger.info("Protocol: VAD Uplink Enabled.")
        
        while self._running:
            try:
                frame = await asyncio.wait_for(self._transport.input().get_audio_frame(), timeout=0.1)
                if not frame: continue
                volume = audioop.rms(frame, 2)
                # Sensitivity gate
                if volume > 3000:
                    self._send_queue.put_nowait({"audio": {"data": frame, "mime_type": "audio/pcm"}})
                    self._last_frame_time = time.time()
                    self._in_turn = True
            except asyncio.TimeoutError: continue
            except Exception as e:
                logger.error(f"Input error: {e}")
                self._running = False
                break

    async def _silence_watchdog(self):
        while self._running:
            await asyncio.sleep(0.05)
            # 1.0s prevents phonetic clipping in multi-turn tools
            if self._in_turn and (time.time() - self._last_frame_time) > 1.0:
                logger.debug("Protocol: Silence Trigger -> End Stream Segment.")
                self._send_queue.put_nowait({"audio_stream_end": True})
                self._in_turn = False

    async def _sdk_loop(self):
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
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Fenrir"
                    )
                )
            ),
            response_modalities=["AUDIO"]
        )

        while self._running:
            logger.info(f"Protocol: Handshake Initiated (Model: {self._model_id})")
            try:
                async with self._client.aio.live.connect(model=self._model_id, config=config) as session:
                    logger.info("Protocol: Session READY (Interactive Lock Achieved).")
                    self._session_active = True
                    await self._transport.input().start()
                    
                    await asyncio.gather(
                        self._send_realtime(session),
                        self._receive_loop(session)
                    )
                    logger.info("Protocol: Session Cycle Reset.")
            except Exception as e:
                logger.error(f"Protocol: Handshake Failure/Hangup: {e}")
                await asyncio.sleep(2)

async def main(host, port, name, channel):
    mumble = pymumble_py3.Mumble(host=host, user=name, port=port)
    mumble.set_receive_sound(True)
    mumble.start()
    mumble.is_ready()
    logger.info(f"Mumble Host: {host} (Identity: {name})")
    
    transport = MumbleTransport(mumble)
    ready_event = asyncio.Event()
    
    async def presence_manager():
        # Force position in room
        target_channel = channel
        while mumble.is_alive():
            try:
                try:
                    ch = mumble.channels.find_by_name(target_channel)
                except Exception:
                    ch = None

                if not ch:
                    # SPEC: Fallback to Audience if AI Test Room is missing
                    if target_channel == "AI Test Room":
                        logger.warning("Presence: 'AI Test Room' not found. Falling back to 'Audience 👂' per SPEC.")
                        target_channel = "Audience 👂"
                        continue
                    else:
                        logger.error(f"Presence: Target channel '{target_channel}' not found.")
                else:
                    ch.move_in()
                    # Wait until we are actually in the channel
                    while mumble.is_alive():
                        myself = mumble.users.myself
                        if myself and 'channel_id' in myself and myself['channel_id'] == ch['channel_id']:
                            break
                        await asyncio.sleep(0.2)
                    break
            except Exception as e:
                logger.error(f"Presence setup error: {e}")
            await asyncio.sleep(1)
        
        while mumble.is_alive() and not mumble.users.myself: await asyncio.sleep(0.5)
        mumble.users.myself.deafen()
        mumble.users.myself.mute()
        await asyncio.sleep(2.5)
        
        mumble.users.myself.undeafen()
        mumble.users.myself.unmute()
        logger.info("Presence: Operational.")
        ready_event.set()
        
        while mumble.is_alive(): await asyncio.sleep(2)
        sys.exit(1)

    system_instruction = (
        "You are Benny Botman. Respond VERBALLY and IMMEDIATELY. "
        "MANDATE: Explicitly state actions before taking them. "
        "Multimodal continuity is critical."
    )
    
    processor = GeminiSDKProcessor(transport, mumble, "gemini-3.1-flash-live-preview", system_instruction, ready_event)
    
    await asyncio.gather(
        presence_manager(),
        processor._sdk_loop(),
        processor._process_input_audio(),
        processor._silence_watchdog()
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="murmur")
    parser.add_argument("--port", type=int, default=64738)
    parser.add_argument("--name", default="Benny Bot v14")
    parser.add_argument("--channel", default="AI Test Room")
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.host, args.port, args.name, args.channel))
    except (KeyboardInterrupt, SystemExit):
        pass
