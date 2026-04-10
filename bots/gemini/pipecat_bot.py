import asyncio
import os
import sys
import argparse
import signal
from loguru import logger
from dotenv import load_dotenv

import pymumble_py3 as pymumble
import pymumble_py3.constants

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.logger import FrameLogger
from pipecat.transports.base_transport import TransportParams
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService, GeminiVADParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import LLMRunFrame, EndFrame, TextFrame, LLMContextFrame, StartFrame, InputAudioRawFrame, ErrorFrame
from pipecat.processors.frame_processor import FrameProcessor
import time
import traceback

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
        # Enable sound reception explicitly
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

class StartFrameDetector(FrameProcessor):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame):
            logger.info("Pipeline StartFrame detected!")
            await self._callback()

class GlobalErrorMonitor(FrameProcessor):
    async def process_frame(self, frame, direction):
        if isinstance(frame, ErrorFrame):
            logger.error(f"PIPELINE ERROR DETECTED: {frame.error}")
            # We don't stop the pipeline here, just ensure it's logged.
        return await self.push_frame(frame, direction)


async def main(host, port, name, channel):
    mumble_wrapper = PymumbleWrapper(host, port, name, channel)
    mumble_wrapper.start()

    pipeline_ready = asyncio.Event()
    async def on_pipeline_start():
        # ALIGNMENT: Passive connection. We rely on the initial config 
        # mapping to trigger the model, mirroring the SDK script.
        logger.info("Pipeline started. Interaction ready.")
        pipeline_ready.set()






    # Context initialization
    prompt_path = os.path.join(os.path.dirname(__file__), "SYSTEM_PROMPT.md")
    with open(prompt_path, "r") as f:
        system_instruction = f.read()
    
    context = LLMContext()



    # Move to the requested channel with fallback per SPEC
    async def join_channel_task(task):
        logger.info(f"Targeting channel: {channel}")
        found = False
        
        # Phase 1: Try Primary Target for 20s
        for attempt in range(10):
            try:
                ch = mumble_wrapper.mumble.channels.find_by_name(channel)
                if ch:
                    ch.move_in()
                    logger.info(f"Presence Success: Moved to PRIMARY '{channel}' (ID: {ch['channel_id']})")
                    found = True
                    break
            except:
                logger.debug(f"Presence Wait: Primary '{channel}' not found (Attempt {attempt+1}/10)")
                await asyncio.sleep(2)
        
        # Phase 2: Fallback to Audience
        if not found:
            try:
                fallback = "Audience 👂"
                ch = mumble_wrapper.mumble.channels.find_by_name(fallback)
                if ch:
                    ch.move_in()
                    logger.info(f"Presence Success: Fell back to '{fallback}' (ID: {ch['channel_id']})")
                    found = True
            except Exception as e:
                logger.error(f"Presence Failure: Could not join primary or fallback: {e}")
        
        if not found:
            logger.error("Could not find any suitable channel. Bot will stay in Root.")
        
        # Wait for pipeline to be ready and Mumble sync
        logger.info("Waiting for pipeline and Gemini session to start...")
        try:
            # 2. Wait for bootstrap to complete and services to stabilize
            await asyncio.wait_for(pipeline_ready.wait(), timeout=15)
            
            # Wait for Mumble synchronization
            while not mumble_wrapper.mumble.users.myself:
                await asyncio.sleep(0.5)
            
            # Small delay to ensure the Gemini websocket is ready after bootstrap
            await asyncio.sleep(1.0)
            
            # Unmute immediately - session is now Running
            myself = mumble_wrapper.mumble.users.myself
            myself.unmute()
            myself.undeafen()
            myself['self_mute'] = False
            myself['self_deaf'] = False
            
            logger.info("Benny is now UNMUTED and LISTENING.")


        except asyncio.TimeoutError:
            logger.error("Pipeline OR Mumble sync timed out.")
        except Exception as e:
            logger.error(f"Error during unmuting/initialization: {e}", exc_info=True)






    # Set up signal handlers for clean exit
    def signal_handler():
        logger.info("Received termination signal. Shutting down...")
        if mumble_wrapper.mumble:
            mumble_wrapper.mumble.stop()
        sys.exit(0)

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        pass # Signal handlers not supported on all platforms/loops

    # Restore correct model identifier and production parameters
    # ALIGNMENT: Match the working SDK script exactly
    llm = GeminiLiveLLMService(
        api_key=os.getenv("GEMINI_API_KEY"),
        inference_on_context_initialization=False, # ALIGNMENT: Disable redundant initial turn
        settings=GeminiLiveLLMService.Settings(
            model="models/gemini-3.1-flash-live-preview",
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=system_instruction)],
                role="user" # ALIGNMENT: The secret role trigger
            ),
            voice="Charon",
            media_resolution="MEDIA_RESOLUTION_MEDIUM"
        )
    )










    # Initialize custom Mumble Transport
    params = TransportParams(
        audio_out_enabled=True,
        audio_in_enabled=True,
        audio_in_passthrough=True
    )
    transport = MumbleTransport(mumble_wrapper.mumble, params)

    class FrameCounter(FrameProcessor):
        def __init__(self, name):
            super().__init__()
            self._name = name
            self._count = 0
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, InputAudioRawFrame):
                self._count += 1
                if self._count <= 5 or self._count % 50 == 0:
                    logger.debug(f"FrameCounter [{self._name}]: Audio Frame #{self._count} sent to LLM")
            return await self.push_frame(frame, direction)

    counter = FrameCounter("LLM-Input")

    # Pipeline order: 
    # 1. Transport Input
    # 2. StartFrameDetector (triggers bootstrap immediately to avoid deadlock)
    # 3. LLM Service (handles multimodal auth and processing)
    # 4. FrameLogger (to verify output)
    # 5. Transport Output
    pipeline = Pipeline([
        transport.input(),
        StartFrameDetector(on_pipeline_start),
        llm,
        FrameLogger("From LLM"),
        transport.output(),
        GlobalErrorMonitor(),
    ])











    task = PipelineTask(pipeline, params=PipelineParams(
        enable_metrics=True,
        enable_usage_metrics=True,
    ))

    # Run channel joiner in background
    def task_done_callback(t):
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"BACKGROUND TASK CRASHED: {t.get_name()} - {e}")
            traceback.print_exc()

    jct = asyncio.create_task(join_channel_task(task), name="join_channel_task")
    mut = asyncio.create_task(monitor_users(mumble_wrapper), name="monitor_users")
    jct.add_done_callback(task_done_callback)
    mut.add_done_callback(task_done_callback)

    runner = PipelineRunner()
    
    logger.info("Pipeline Status: Starting runner...")
    try:
        await runner.run(task)
    except Exception as e:
        logger.critical(f"PIPELINE RUNNER FATAL ERROR: {e}")
        traceback.print_exc()
    finally:
        logger.info("Runner finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benny Botman Pipecat Edition")
    parser.add_argument("--host", default="murmur", help="Mumble server host")
    parser.add_argument("--port", type=int, default=64738, help="Mumble server port")
    parser.add_argument("--name", default="Benny Botman", help="Bot name")
    parser.add_argument("--channel", default="AI Test Room", help="Initial channel")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port, args.name, args.channel))
    except KeyboardInterrupt:
        pass
