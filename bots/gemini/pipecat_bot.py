import sys
import os
import asyncio
import logging
import argparse
from typing import List

from dotenv import load_dotenv

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService, GeminiVADParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, LLMContextFrame, StartFrame, EndFrame, InputAudioRawFrame, TTSAudioRawFrame, LLMMessagesAppendFrame
from pipecat.transports.base_transport import TransportParams
import audioop
import time

# Import our custom transport
from mumble_transport import MumbleTransport

import pymumble_py3 as pymumble

from loguru import logger
import logging

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# Intercept standard logging
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
logger.info("Logging interceptor configured")

class PymumbleWrapper:
    def __init__(self, host, port, name, cert_file, key_file):
        self.mumble = pymumble.Mumble(
            host, 
            name, 
            port=port, 
            certfile=cert_file, 
            keyfile=key_file,
            reconnect=True
        )
        self.mumble.set_receive_sound(True)
    
    def start(self):
        self.mumble.start()
        self.mumble.is_ready()
        self.mumble.users.myself.mute()
        
    def stop(self):
        self.mumble.stop()


async def main(host, port, name, channel_name):
    # Load environment variables
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GOOGLE_API_KEY:
        logger.error("GEMINI_API_KEY not found in environment")
        sys.exit(1)

    CERT_FILE = "/bots/certs/benny.pem"
    KEY_FILE = "/bots/certs/benny_key.pem"

    # 1. Initialize Mumble
    mumble_wrapper = PymumbleWrapper(host, port, name, CERT_FILE, KEY_FILE)
    mumble_wrapper.start()
    logger.info(f"Mumble Connected to {host}:{port} as {name}")

    # Move to channel if provided (with retries for AI Test Room)
    target_chan_id = None
    async def join_channel():
        nonlocal target_chan_id
        logger.info(f"Presence Check: Attempting to join channel '{channel_name}'...")
        while True:
            try:
                target_chan = mumble_wrapper.mumble.channels.find_by_name(channel_name)
                target_chan_id = target_chan['channel_id']
                mumble_wrapper.mumble.users.myself.move_in(target_chan_id)
                logger.info(f"Presence Success: Moved to '{channel_name}' (ID: {target_chan_id})")
                return
            except Exception:
                if channel_name == "AI Test Room":
                    # Keep waiting for the test script to create it
                    logger.debug(f"Presence Wait: '{channel_name}' not found yet. Retrying in 2s...")
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.warning(f"Presence Failure: Could not move to channel '{channel_name}'")
                    return

    # Start join task but don't block initialization
    asyncio.create_task(join_channel())

    # 2. Initialize Transport
    transport = MumbleTransport(
        mumble_wrapper.mumble,
        TransportParams(audio_in_enabled=True, audio_out_enabled=True)
    )

    # 3. Initialize Services
    try:
        with open("SYSTEM_PROMPT.md", "r") as f:
            system_instruction = f.read()
    except:
        system_instruction = "You are Benny Botman, a helpful AI podcasting assistant. Keep responses concise and natural."

    llm = GeminiLiveLLMService(
        api_key=GOOGLE_API_KEY,
        inference_on_context_initialization=True,
        settings=GeminiLiveLLMService.Settings(
            model="models/gemini-2.5-flash-native-audio-preview-12-2025",
            system_instruction=system_instruction,
            voice="Puck"
        )
    )




    # 4. Context & Aggregators
    context = LLMContext(
        messages=[{"role": "system", "content": system_instruction}]
    )
    context_aggregator = LLMContextAggregatorPair(context)

    from pipecat.processors.logger import FrameLogger

    # 5. Pipeline
    pipeline = Pipeline(
        [
            transport.input(),
            FrameLogger("Input"),
            llm,
            transport.output(),
        ]
    )



    # 6. Task & Runner
    runner = PipelineRunner()
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_usage_metrics=True,
            enable_performance_metrics=True,
        )
    )

    # Presence Indicators: Couple Mumble Mute to LLM Session
    # Since this version of Pipecat doesn't have a direct 'on_session_started' event,
    # we wrap the internal _handle_session_ready method.
    original_handle_ready = llm._handle_session_ready
    async def wrapped_handle_ready(session):
        await original_handle_ready(session)
        logger.info(f"Gemini Live: Session ready. Current Mumble state: Muted={mumble_wrapper.mumble.users.myself['self_mute']}")
        
        # Explicitly unmute and undeafen
        mumble_wrapper.mumble.users.myself.unmute()
        mumble_wrapper.mumble.users.myself.undeafen()
        
        # Verify local state update
        logger.info(f"Gemini Live: Action sent. New Mumble state: Muted={mumble_wrapper.mumble.users.myself['self_mute']}")
    
    # Apply the wrapper
    llm._handle_session_ready = wrapped_handle_ready

    try:
        # Pre-start initialization
        mumble_wrapper.mumble.is_ready()
        # Keep muted until LLM is ready
        mumble_wrapper.mumble.users.myself.mute()
        logger.info("Mumble Presence: Bot verified and waiting for LLM session...")
        
        logger.info("Pipeline Status: Starting...")
        await runner.run(task)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
    finally:
        logger.info("Stopping Mumble...")
        mumble_wrapper.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benny Botman (Pipecat)")
    parser.add_argument("--host", default="murmur", help="Mumble server host")
    parser.add_argument("--port", type=int, default=64738, help="Mumble server port")
    parser.add_argument("--name", default="Benny Botman", help="Bot name")
    parser.add_argument("--channel", default="AI Test Room", help="Channel to join")
    args = parser.parse_args()

    asyncio.run(main(args.host, args.port, args.name, args.channel))
