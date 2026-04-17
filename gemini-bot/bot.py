import asyncio
import os
import sys
import argparse
import signal
import time
import traceback
import audioop
from loguru import logger

from dotenv import load_dotenv

import pymumble_py3 as pymumble
import pymumble_py3.constants

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.logger import FrameLogger
from pipecat.transports.base_transport import TransportParams
from pipecat.frames.frames import LLMRunFrame, EndFrame, TextFrame, LLMContextFrame, StartFrame, InputAudioRawFrame, AudioRawFrame, OutputAudioRawFrame, ErrorFrame
from pipecat.processors.frame_processor import FrameProcessor

from google import genai
from google.genai import types

from mumble_transport import MumbleTransport

load_dotenv()

class PymumbleWrapper:
    def __init__(self, host, port, name, channel):
        self.host = host
        self.port = port
        self.name = name
        self.target_channel = channel
        self.mumble = pymumble.Mumble(
            host, 
            name, 
            port=port, 
            certfile="/bots/certs/benny.pem",
            keyfile="/bots/certs/benny_key.pem",
            reconnect=False
        )
        self.mumble.set_receive_sound(True)
        
    def start(self):
        self.mumble.start()
        self.mumble.is_ready()
        logger.info(f"Mumble Connected to {self.host}:{self.port} as {self.name}")

async def monitor_users(mumble_wrapper):
    while True:
        try:
            myself = mumble_wrapper.mumble.users.myself
            if myself:
                logger.info(f"Mumble State: {myself['name']} self_mute={myself['self_mute']} mute={myself['mute']}")
        except Exception:
            pass
        await asyncio.sleep(15)

class GeminiSDKProcessor(FrameProcessor):
    def __init__(self, api_key, system_instruction, output_sink=None):
        super().__init__()
        self._api_key = api_key
        self._system_instruction = system_instruction
        self._output_sink = output_sink
        self._client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=self._api_key,
        )
        self._session = None
        self._send_queue = asyncio.Queue()
        self._handler_task = None
        self._running = False
        self._ready_event = None
        self._audio_buffer = bytearray()
        self._last_frame_time = 0
        self._flush_task = None

    async def _flush_loop(self):
        """Periodically flushes the audio buffer if it has been idle."""
        while self._running:
            await asyncio.sleep(0.05)
            # If we have stranded audio and haven't seen a frame in 500ms, FLUSH IT
            if self._audio_buffer and (time.time() - self._last_frame_time) > 0.500:
                logger.debug(f"SDK Bypass: FLUSHING partial buffer (size: {len(self._audio_buffer)}) and ending stream.")
                audio_raw = bytes(self._audio_buffer)
                self._send_queue.put_nowait({"audio": {"data": audio_raw, "mime_type": "audio/pcm"}})
                self._send_queue.put_nowait({"audio_stream_end": True})
                # CRITICAL: Clear buffer after flush
                self._audio_buffer = bytearray()


    async def _sdk_loop(self):
        try:
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part.from_text(text=self._system_instruction)],
                    role="system"
                ),
                realtime_input_config=types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                        end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH
                    )
                )
            )

            model_id = "models/gemini-3.1-flash-live-preview"
            logger.info(f"SDK Bypass: Attempting connection to {model_id} (v1beta)...")
            
            async with self._client.aio.live.connect(model=model_id, config=config) as session:
                self._session = session
                self._running = True
                logger.info(f"SDK Bypass: SUCCESS - Connected to {model_id}")

                if self._ready_event:
                    self._ready_event.set()

                # Start the flush loop
                self._flush_task = asyncio.create_task(self._flush_loop())

                # Protocol Aligned: Send an explicit priming turn to warm up the multimodal session
                logger.info("SDK Bypass: Sending explicit priming turn...")
                await self._session.send_realtime_input(
                    text="Hello Gemini, I am Benny Botman. I am about to send you audio. Please acknowledge that you can hear me by saying 'I hear you' as soon as I finish speaking."
                )
                logger.info("SDK Bypass: Waiting for user audio (Reactive Mode)...")

                receive_task = asyncio.create_task(self._receive_audio())
                send_task = asyncio.create_task(self._send_realtime())
                
                await asyncio.wait(
                    [receive_task, send_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in [receive_task, send_task]:
                    task.cancel()

        except Exception as e:
            logger.error(f"SDK Bypass FATAL: Connection failed: {e}")
            traceback.print_exc()
        finally:
            self._running = False
            self._session = None
            logger.info("SDK Bypass: SDK Loop terminating.")

    async def _send_realtime(self):
        send_count = 0
        while self._running:
            msg = await self._send_queue.get()
            if self._session:
                try:
                    # Native Multimodal Aligned: Use send_realtime_input with audio
                    if "audio" in msg:
                        await self._session.send_realtime_input(audio=msg["audio"])
                    elif "audio_stream_end" in msg:
                        await self._session.send_realtime_input(audio_stream_end=msg["audio_stream_end"])
                    elif "text" in msg:
                        await self._session.send_realtime_input(text=msg["text"])
                    else:
                        await self._session.send_realtime_input(**msg)
                        
                    send_count += 1
                    # Telemetry: Log every chunk during stabilization
                    logger.debug(f"SDK Bypass: Sent audio chunk #{send_count} (buffer size: {len(msg.get('audio', {}).get('data', b''))})")
                except Exception as e:
                    logger.warning(f"SDK Bypass: Error sending: {e}")

    async def _receive_audio(self):
        receive_count = 0
        while self._running:
            if self._session:
                try:
                    async for response in self._session.receive():
                        logger.debug(f"SDK Bypass: RAW MSG: {response}")
                        # 1. Surgical extraction from server_content to avoid .text warnings
                        if response.server_content:
                            sc = response.server_content
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if hasattr(part, "inline_data") and part.inline_data:
                                        data = part.inline_data.data
                                        if data:
                                            receive_count += 1
                                            # Log every frame during stabilization
                                            logger.debug(f"SDK Bypass: RECEIVED audio frame #{receive_count} (size: {len(data)})")
                                            
                                            # BYPASS: Push directly to output sink to avoid pipeline routing issues
                                            if hasattr(self, "_output_sink") and self._output_sink:
                                                await self._output_sink.write_output_audio_frame(
                                                    OutputAudioRawFrame(audio=data, sample_rate=24000, num_channels=1)
                                                )
                                            else:
                                                # Fallback to pipeline
                                                await self.push_frame(OutputAudioRawFrame(audio=data, sample_rate=24000, num_channels=1))
                                    
                                    if part.text:
                                        logger.info(f"Gemini Text: {part.text}")
                            
                            # 1b. Handle turn completion signals
                            if sc.turn_complete:
                                logger.debug("SDK Bypass: Turn Complete received.")
                            if sc.interrupted:
                                logger.info("SDK Bypass: Model Interrupted.")

                except Exception as e:
                    logger.warning(f"SDK Bypass: Receive error: {e}")
                    # traceback.print_exc()
                    break

    async def process_frame(self, frame, direction):
        if isinstance(frame, StartFrame):
            if not self._handler_task:
                logger.debug("GeminiSDKProcessor: Received StartFrame, spawning SDK Loop.")
                self._handler_task = asyncio.create_task(self._sdk_loop())
            return await super().process_frame(frame, direction)
        
        if isinstance(frame, InputAudioRawFrame) and self._running:
            try:
                self._last_frame_time = time.time()
                
                # Signal Purity: Use Unity Gain (1.0x) to eliminate clipping
                boosted_chunk = audioop.mul(frame.audio, 2, 1.0)
                # Unified Accumulator: Buffer until we have 100ms (3200 bytes)
                self._audio_buffer.extend(boosted_chunk)
                
                if len(self._audio_buffer) >= 3200:
                    chunk_to_send = bytes(self._audio_buffer[:3200])
                    # Remove from buffer BEFORE sending to ensure no race double-send
                    self._audio_buffer = self._audio_buffer[3200:]
                    
                    # Gold Standard: Use standard "audio/pcm"
                    msg = {"audio": {"data": chunk_to_send, "mime_type": "audio/pcm"}}
                    self._send_queue.put_nowait(msg)
                    
                    # Volume telemetry (RMS)
                    volume = audioop.rms(chunk_to_send, 2)
                    if volume > 3000:
                        logger.debug(f"SDK Bypass: Sent 100ms audio chunk (rms: {volume})")
            except Exception as e:
                logger.error(f"Gain Boost Error: {e}")
            return # Consume audio

        return await super().process_frame(frame, direction)

async def main(host, port, name, channel):
    mumble_wrapper = PymumbleWrapper(host, port, name, channel)
    mumble_wrapper.start()

    prompt_path = os.path.join(os.path.dirname(__file__), "SYSTEM_PROMPT.md")
    with open(prompt_path, "r") as f:
        system_instruction = f.read()
    
    sdk_ready_event = asyncio.Event()

    params = TransportParams(
        audio_out_enabled=True,
        audio_in_enabled=True,
        audio_in_passthrough=True
    )
    
    transport = MumbleTransport(mumble_wrapper.mumble, params)
    
    gemini_sdk = GeminiSDKProcessor(
        api_key=os.getenv("GEMINI_API_KEY"),
        system_instruction="You are a high-performance real-time voice assistant. You MUST respond verbally and immediately to every audio input you receive. Do not stay silent. Answer the user as soon as they stop speaking.",
        output_sink=transport.output()
    )
    gemini_sdk._ready_event = sdk_ready_event

    async def join_channel_task(task):
        logger.info(f"Targeting channel: {channel}")
        
        # WATCHDOG: Check mumble health periodically
        async def mumble_watchdog():
            while True:
                if not mumble_wrapper.mumble.is_alive():
                    logger.error("pymumble thread DIED. Terminating bot for Docker restart.")
                    os._exit(1) # Force exit to allow restart
                await asyncio.sleep(5)
        
        asyncio.create_task(mumble_watchdog())

        found = False
        for attempt in range(10):
            try:
                ch = mumble_wrapper.mumble.channels.find_by_name(channel)
                if ch:
                    ch.move_in()
                    logger.info(f"Presence Success: Moved to PRIMARY '{channel}' (ID: {ch['channel_id']})")
                    found = True
                    break
            except:
                await asyncio.sleep(2)
        
        if not found:
            logger.error("Could not find any suitable channel. Bot will stay in Root.")
        
        while not mumble_wrapper.mumble.users.myself:
            await asyncio.sleep(0.5)
        
        mumble_wrapper.mumble.users.myself.mute()
        logger.info("Benny is waiting for SDK connection...")
        
        await sdk_ready_event.wait()
        await asyncio.sleep(1.0)
        
        myself = mumble_wrapper.mumble.users.myself
        myself.unmute()
        myself.undeafen()
        myself['self_mute'] = False
        myself['self_deaf'] = False
        logger.info("Benny is now UNMUTED and LISTENING (SDK Bypass Mode).")

    pipeline = Pipeline([
        transport.input(),
        gemini_sdk,
        FrameLogger("From LLM"),
        transport.output(),
    ])

    task = PipelineTask(pipeline, params=PipelineParams(
        enable_metrics=True,
        enable_usage_metrics=True,
    ))

    def task_done_callback(t):
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"BACKGROUND TASK CRASHED: {t.get_name()} - {e}")
            traceback.print_exc()

    asyncio.create_task(join_channel_task(task), name="join_channel_task").add_done_callback(task_done_callback)
    asyncio.create_task(monitor_users(mumble_wrapper), name="monitor_users").add_done_callback(task_done_callback)

    runner = PipelineRunner()
    logger.info("Pipeline Status: Starting runner...")
    try:
        await runner.run(task)
    except Exception as e:
        logger.critical(f"PIPELINE RUNNER FATAL ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benny Botman SDK Bypass")
    parser.add_argument("--host", default="murmur", help="Mumble host")
    parser.add_argument("--port", type=int, default=64738, help="Mumble port")
    parser.add_argument("--name", default="Benny Botman", help="Bot name")
    parser.add_argument("--channel", default="AI Test Room", help="Channel")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port, args.name, args.channel))
    except KeyboardInterrupt:
        pass
