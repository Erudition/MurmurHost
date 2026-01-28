import time
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
import os

HOST = os.getenv("MUMBLE_HOST", "murmur")
USER = os.getenv("MUMBLE_USER", "Echo") # Allow dynamic naming if needed
MIC_CHECK_CHANNEL = "Mic Check 🎧"

class SimpleEchoBot:
    def __init__(self):
        self.mumble = None
        self.is_running = True
        
    def connect(self):
        print(f"EchoBot: Connecting to {HOST} as {USER}...")
        self.mumble = pymumble.Mumble(HOST, USER, port=64738, reconnect=True)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        self.mumble.start()
        
    def connected(self):
        print("EchoBot: Connected!")
        self.mumble.set_receive_sound(True)
        try:
            target = self.mumble.channels.find_by_name(MIC_CHECK_CHANNEL)
            if target:
                self.mumble.channels[target['channel_id']].move_in()
        except: pass

    def sound_received(self, user, sound):
        # ECHO: Bounce audio back
        self.mumble.sound_output.add_sound(sound.pcm)

    def run(self):
        self.connect()
        while self.is_running and self.mumble.is_alive():
            time.sleep(1)

if __name__ == "__main__":
    bot = SimpleEchoBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        pass
