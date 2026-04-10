import time
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
import os
import sys

HOST = os.getenv("MUMBLE_HOST", "murmur")
USER = os.getenv("MUMBLE_USER", "Echo") # Allow dynamic naming if needed
MIC_CHECK_CHANNEL = "Mic Check 🎧"

class SimpleEchoBot:
    def __init__(self):
        self.mumble = None
        self.is_running = True
        self.first_sound_times = {}
        self.verified = set()
        self.audio_buffers = {} # username -> bytearray
        self.last_audio_times = {} # username -> float
        self.is_parroting = {} # username -> bool
        
    def connect(self):
        print(f"EchoBot: Connecting to {HOST} as {USER}...")
        
        # Use persistent certificate for identity
        cert_file = "/bots/certs/echo.pem"
        key_file = "/bots/certs/echo_key.pem"
        
        self.mumble = pymumble.Mumble(HOST, USER, port=64738, reconnect=False,
                                       certfile=cert_file, keyfile=key_file)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        self.mumble.set_receive_sound(True)  # CRITICAL: Must be True before .start() to init SoundOutput
        self.mumble.start()
        
    def connected(self):
        print("EchoBot: Connected!")
        try:
            target = self.mumble.channels.find_by_name(MIC_CHECK_CHANNEL)
            if target:
                self.mumble.channels[target['channel_id']].move_in()
        except: pass

    def sound_received(self, user, sound):
        try:
            name = user['name']
            if not name: return

            # 1. INTERRUPTION: If user speaks while we are parroting, kill the output
            if self.is_parroting.get(name):
                self.mumble.sound_output.clear_buffer()
                self.is_parroting[name] = False
                self.audio_buffers[name] = bytearray()
                print(f"EchoBot: Interrupted by {name}. Clearing buffer.")

            # 2. MODE HANDLING
            if name in self.verified:
                # PARROT: Buffer audio
                if name not in self.audio_buffers:
                    self.audio_buffers[name] = bytearray()
                self.audio_buffers[name].extend(sound.pcm)
                self.last_audio_times[name] = time.time()
            else:
                # ECHO: Instant loopback for unverified users
                self.mumble.sound_output.add_sound(sound.pcm)
            
            # 3. VERIFICATION Transition
            if name not in self.verified:
                if name not in self.first_sound_times:
                    self.first_sound_times[name] = time.time()
                elif time.time() - self.first_sound_times[name] > 3.0:
                    print(f"EchoBot: Verifying {name}...")
                    self.verified.add(name)
                    user.send_text_message("Mic Checked - I can hear you! Switching to Parrot Mode.")
                    # Notify Supervisor
                    self.notify_supervisor(name)
                    
        except Exception as e:
            print(f"EchoBot Error: {e}")

    def notify_supervisor(self, username):
        supervisor = None
        for u in self.mumble.users.values():
            try:
                if u['name'] == "Supervisor":
                    supervisor = u
                    break
            except: pass
        
        if supervisor:
            supervisor.send_text_message(f"!verify_user {username}")
        else:
            print("EchoBot: Supervisor not found to notify.")

    def run(self):
        self.connect()
        while self.is_running:
            if not self.mumble.is_alive():
                print("EchoBot: Mumble thread died. Exiting for Supervisor restart.")
                sys.exit(1)
            
            # Parrot Trigger Logic (50-80ms silence detection)
            now = time.time()
            for name in list(self.last_audio_times.keys()):
                if name in self.audio_buffers and len(self.audio_buffers[name]) > 0:
                    # If silence threshold reached and not currently marked as parroting
                    if now - self.last_audio_times[name] > 0.08:
                        print(f"EchoBot: Parrotting {len(self.audio_buffers[name])} bytes to {name}")
                        self.mumble.sound_output.add_sound(bytes(self.audio_buffers[name]))
                        self.audio_buffers[name] = bytearray()
                        self.is_parroting[name] = True
            
            # Check if playback finished (to reset is_parroting)
            if hasattr(self.mumble, 'sound_output') and self.mumble.sound_output and self.mumble.sound_output.get_buffer_size() == 0:
                for name in self.is_parroting:
                    self.is_parroting[name] = False

            time.sleep(0.01) # 10ms resolution

if __name__ == "__main__":
    bot = SimpleEchoBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        pass
