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
# Look for any opus file in recordings if default not found
DEFAULT_AUDIO = "/bots/test-speech-clips/check-check-123.opus"

class TestingBot:
    def __init__(self):
        self.mumble = None
        self.is_running = True
        
    async def connect(self, name):
        print(f"TestingBot ({name}): Connecting to {MUMBLE_HOST}...")
        self.mumble = pymumble.Mumble(MUMBLE_HOST, name, port=64738)
        self.mumble.start()
        await asyncio.to_thread(self.mumble.is_ready)
        self.mumble.users.myself.unmute()
        print("TestingBot: Connected and Unmuted.")

    async def play_audio(self, audio_path=None):
        """Pipes PCM audio from an Ogg/Opus file to Mumble."""
        # Always unmute before playback
        self.mumble.users.myself.unmute()
        await asyncio.sleep(0.1)
        
        target_audio = audio_path if audio_path else DEFAULT_AUDIO
        
        if not os.path.exists(target_audio):
             # Try to find any opus file in recordings
             recordings_dir = "/bots/recordings"
             if os.path.exists(recordings_dir):
                 for root, dirs, files in os.walk(recordings_dir):
                     for f in files:
                         if f.endswith(".opus"):
                             target_audio = os.path.join(root, f)
                             break
                     if target_audio != DEFAULT_AUDIO: break

        if not os.path.exists(target_audio):
            print(f"TestingBot: Audio file {target_audio} not found. Skipping audio test.")
            return

        print(f"TestingBot: Playing {target_audio}...")
        # Use ffmpeg to decode opus to s16le PCM at 48000Hz (Mumble native)
        cmd = [
            "ffmpeg", "-i", target_audio,
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
        await self.connect(self.BOT_NAME)
        
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
                await asyncio.sleep(5) # Wait for bots to join
                
                # 4. Speak on Stage to trigger Benny
                print("TestingBot: Speaking on Stage...")
                await self.play_audio()
                await asyncio.sleep(10)
                
                # 5. Play more audio
                await self.play_audio()
                await asyncio.sleep(30)
                
        except Exception as e:
            print(f"TestingBot Error: {e}")
        
        print("TestingBot: Scenario complete. Staying online for manual check.")
        while self.is_running:
            await asyncio.sleep(10)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default=BOT_NAME)
    args = parser.parse_args()
    
    bot = TestingBot()
    bot.BOT_NAME = args.name
    try:
        asyncio.run(bot.run_scenario())
    except KeyboardInterrupt:
        pass
