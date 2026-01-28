import asyncio
import os
import sys
import time
import subprocess
import pymumble_py3 as pymumble
from pymumble_py3.constants import *

# Configuration
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_NAME = "TestingBot"
TEST_AUDIO = "/bots/recordings/podcast-20260126-022042-Connor.opus"

class TestingBot:
    def __init__(self):
        self.mumble = None
        self.is_running = True
        
    async def connect(self):
        print(f"TestingBot: Connecting to {MUMBLE_HOST}...")
        self.mumble = pymumble.Mumble(MUMBLE_HOST, BOT_NAME, port=64738)
        self.mumble.start()
        await asyncio.to_thread(self.mumble.is_ready)
        print("TestingBot: Connected.")

    async def play_audio(self):
        """Pipes PCM audio from an Ogg/Opus file to Mumble."""
        if not os.path.exists(TEST_AUDIO):
            print(f"TestingBot: Audio file {TEST_AUDIO} not found. Skipping audio test.")
            return

        print(f"TestingBot: Playing {TEST_AUDIO}...")
        # Use ffmpeg to decode opus to s16le PCM at 48000Hz (Mumble native)
        cmd = [
            "ffmpeg", "-i", TEST_AUDIO,
            "-f", "s16le", "-ac", "1", "-ar", "48000", "-"
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        while True:
            # Read 960 samples (20ms) -> 1920 bytes
            data = proc.stdout.read(1920)
            if not data: break
            self.mumble.sound_output.add_sound(data)
            await asyncio.sleep(0.015) # Slightly faster than 20ms to stay ahead of buffer
            
        proc.wait()
        print("TestingBot: Finished playing audio.")

    async def run_scenario(self):
        await self.connect()
        
        # Scenario: 
        # 1. Join Mic Check
        try:
            target = self.mumble.channels.find_by_name("Mic Check 🎧")
            if target:
                print("TestingBot: Moving to Mic Check...")
                self.mumble.channels[target['channel_id']].move_in()
                await asyncio.sleep(2)
                
                # 2. Play Audio to trigger verification
                await self.play_audio()
                await asyncio.sleep(5)
                
            # 3. Move to Stage to trigger Recording/PodBot
            target = self.mumble.channels.find_by_name("🎙️ Stage 🔴")
            if target:
                print("TestingBot: Moving to Stage...")
                self.mumble.channels[target['channel_id']].move_in()
                await asyncio.sleep(10)
                
                # 4. Play more audio
                await self.play_audio()
                await asyncio.sleep(30)
                
        except Exception as e:
            print(f"TestingBot Error: {e}")
        
        print("TestingBot: Scenario complete. Staying online for manual check.")
        while self.is_running:
            await asyncio.sleep(10)

if __name__ == "__main__":
    bot = TestingBot()
    try:
        asyncio.run(bot.run_scenario())
    except KeyboardInterrupt:
        pass
