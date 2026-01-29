import asyncio
import os
import time
import subprocess
import pymumble_py3 as pymumble
from pymumble_py3.constants import *

MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_NAME = "VerificationTester"

class VerificationBot:
    def __init__(self):
        self.mumble = None
        self.verified = False
        
    async def connect(self):
        print(f"Connecting to {MUMBLE_HOST} as {BOT_NAME}...")
        cert_file = "/bots/certs/verification.pem"
        key_file = "/bots/certs/verification_key.pem"
        self.mumble = pymumble.Mumble(MUMBLE_HOST, BOT_NAME, port=64738, certfile=cert_file, keyfile=key_file)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.text_received)
        self.mumble.start()
        
        for _ in range(20):
            if self.mumble.is_ready(): break
            await asyncio.sleep(0.5)
            
        if not self.mumble.is_ready():
            print("WARNING: Bot not fully ready, but proceeding...")
        
        self.mumble.users.myself.unmute()
        self.mumble.set_receive_sound(True) # Just in case

    def text_received(self, msg):
        print(f"Received msg: {msg.message}")
        if "Mic Check - I can hear you!" in msg.message:
            self.verified = True
            print("VERIFICATION CONFIRMED!")

    async def play_noise(self, duration=5):
        print(f"Playing noise for {duration}s...")
        # Generate silence/noise using ffmpeg or just send 0 bytes?
        # Supervisor checks RMS, so we need actual noise.
        # Use /bots/test-speech-clips/check-check-123.opus
        audio_path = "/bots/test-speech-clips/check-check-123.opus"
        cmd = ["ffmpeg", "-i", audio_path, "-f", "s16le", "-ac", "1", "-ar", "48000", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        start = time.time()
        while time.time() - start < duration:
            data = proc.stdout.read(1920)
            if not data: 
                # Loop it
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                continue
            self.mumble.sound_output.add_sound(data)
            await asyncio.sleep(0.015)
        
        if proc: proc.terminate()

    async def run(self):
        await self.connect()
        
        # 1. Join Mic Check
        print("Moving to Mic Check...")
        mic_check = self.mumble.channels.find_by_name("Mic Check 🎧")
        if not mic_check:
            print("Mic Check channel not found!")
            return
            
        self.mumble.users.myself.move_in(mic_check['channel_id'])
        await asyncio.sleep(2)
        
        # 2. Check if Echo is Online
        echo_online = any(u['name'] == "Echo" for u in self.mumble.users.values())
        print(f"Echo Bot Online: {echo_online} (Expected: True)")
        
        # 3. Speak to verify
        print("Speaking to verify...")
        await self.play_noise(duration=5)
        
        # 4. Wait for verification
        for _ in range(5):
            if self.verified: break
            await asyncio.sleep(1)
            
        if not self.verified:
            print("FAILED: Did not receive verification message.")
        else:
            print("SUCCESS: User verified.")
            
        # 5. Move out
        print("Moving to Hallway...")
        hallway = self.mumble.channels.find_by_name("Hallway 🖉")
        if hallway:
            self.mumble.users.myself.move_in(hallway['channel_id'])
        
        await asyncio.sleep(5)
        
        # 6. Check if Echo leaves
        echo_online = any(u['name'] == "Echo" for u in self.mumble.users.values())
        print(f"Echo Bot Online: {echo_online} (Expected: False after delay)")
        
        if echo_online:
            print("Waiting another 5s...")
            await asyncio.sleep(5)
            echo_online = any(u['name'] == "Echo" for u in self.mumble.users.values())
            print(f"Echo Bot Online: {echo_online}")

        if not echo_online:
            print("SUCCESS: Echo bot went offline.")
        else:
            print("FAILURE: Echo bot stayed online.")

if __name__ == "__main__":
    t = VerificationBot()
    asyncio.run(t.run())
