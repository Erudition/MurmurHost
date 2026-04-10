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
            # ECHO: Bounce audio back
            self.mumble.sound_output.add_sound(sound.pcm)
            
            # VERIFICATION Logic
            # Using dict-access since Mumble User objects don't always support .get()
            name = user['name']
            if name and name not in self.verified:
                if name not in self.first_sound_times:
                    self.first_sound_times[name] = time.time()
                elif time.time() - self.first_sound_times[name] > 3.0:
                    print(f"EchoBot: Verifying {name}...")
                    self.verified.add(name)
                    user.send_text_message("Mic Check - I can hear you!")
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
            time.sleep(1)

if __name__ == "__main__":
    bot = SimpleEchoBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        pass
