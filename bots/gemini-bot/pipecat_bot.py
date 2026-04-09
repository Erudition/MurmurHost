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
from pipecat.services.google import GeminiLiveLLMService
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.transports.base_transport import TransportParams

# Import our custom transport
from mumble_transport import MumbleTransport

import pymumble_py3 as pymumble

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PipecatBot")

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

    # Move to channel if provided
    try:
        target_chan = mumble_wrapper.mumble.channels.find_by_name(channel_name)
        mumble_wrapper.mumble.users.myself.move_in(target_chan['channel_id'])
        logger.info(f"Moved to channel: {channel_name}")
    except Exception as e:
        logger.warning(f"Could not move to channel {channel_name}: {e}")

    # 2. Initialize Transport
    # MumbleTransport(mumble_client, params)
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

    # Gemini Live Service (0.108+)
    llm = GeminiLiveLLMService(
        api_key=GOOGLE_API_KEY,
        settings=GeminiLiveLLMService.Settings(
            model="gemini-2.5-flash-native-audio-latest",
            voice="Charon",
            system_instruction=system_instruction
        )
    )

    # 4. Context & Aggregators
    context = LLMContext(
        messages=[{"role": "system", "content": system_instruction}]
    )
    
    # Silero VAD (0.108+) - Wrap in VADProcessor
    vad = VADProcessor(vad_analyzer=SileroVADAnalyzer())
    
    # Context Aggregator Pair
    context_aggregator = LLMContextAggregatorPair(context)

    # 5. Pipeline
    # Direct multimodal stream: transport.input() -> llm -> transport.output()
    pipeline = Pipeline(
        [
            transport.input(),
            llm,
            transport.output(),
        ]
    )

    # Runner and Task
    runner = PipelineRunner()
    params = PipelineParams(
        audio_in_sample_rate=16000,
        audio_out_sample_rate=24000
    )
    task = PipelineTask(pipeline, params=params)

    # 6. Event Handlers
    @transport.event_handler("on_connected")
    async def on_connect(transport, client):
        logger.info("Transport connected to Pipecat loop")
        mumble_wrapper.mumble.users.myself.unmute()
        # Trigger an initial response to verify audio path
        initial_context = LLMContext(messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": "Hello! Please say 'Benny is online' to confirm you can hear me."}
        ])
        await task.queue_frame(LLMContextFrame(initial_context))

    @transport.event_handler("on_disconnected")
    async def on_disconnect(transport, client):
        logger.info("Transport disconnected")
        await task.cancel()

    # Initial trigger if needed? Gemini Live usually waits for audio.
    # But we can unmute myself to show we are ready.
    mumble_wrapper.mumble.users.myself.unmute()

    try:
        logger.info("Starting Pipecat pipeline...")
        await runner.run(task)
    except KeyboardInterrupt:
        pass
    finally:
        mumble_wrapper.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benny Botman (Pipecat)")
    parser.add_argument("--host", default="murmur", help="Mumble server host")
    parser.add_argument("--port", type=int, default=64738, help="Mumble server port")
    parser.add_argument("--name", default="Benny Botman", help="Bot name")
    parser.add_argument("--channel", default="AI Test Room", help="Channel to join")
    args = parser.parse_args()

    asyncio.run(main(args.host, args.port, args.name, args.channel))
