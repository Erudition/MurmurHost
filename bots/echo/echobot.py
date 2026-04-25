import os
import sys
import logging
import time
import pymumble_py3 as pymumble
from pymumble_py3.constants import *

# Enable debug logging for pymumble diagnostics
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EchoBot")

class EchoBot:
    def __init__(self, host, port, name, certfile=None, keyfile=None):
        self._host = host
        self._port = port
        self._name = name
        self._certfile = certfile
        self._keyfile = keyfile
        self.mumble = None
        self.is_running = True
        self.verified_users = set()  # Track users who've spoken long enough for Parrot Mode

    def connect(self):
        logger.info(f"EchoBot: Connecting to {self._host}:{self._port} as {self._name}...")
        self.mumble = pymumble.Mumble(host=self._host, port=self._port, user=self._name, certfile=self._certfile, keyfile=self._keyfile)
        
        # Set callbacks
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        
        self.mumble.set_receive_sound(True)  # CRITICAL: Must be True before .start() to init SoundOutput
        self.mumble.start()
        
    def connected(self):
        # Wait for full synchronization
        logger.info("EchoBot: Waiting for server synchronization...")
        self.mumble.is_ready() 
        
        # Identify self session
        myself = self.mumble.users.myself
        session_id = myself.get('session') if myself else "Unknown"
        logger.info(f"EchoBot: Synchronized (Mumble session: {session_id})")

    def sound_received(self, user, sound):
        # Entry heartbeat
        try:
            # DIAGNOSTIC: Log frame receipt from production HEAD
            username = user.get('name', f"ID:{user['session']}")
            pcm_len = len(sound.pcm) if hasattr(sound, 'pcm') and sound.pcm else 0
            
            # ECHO: Bounce audio back immediately
            # Width=2 (16-bit), Rate=48000, Channels=1
            self.mumble.sound_output.add_sound(sound.pcm)
            
        except Exception as e:
            logger.error(f"EchoBot Callback Error: {e}")

    def run(self):
        self.connect()
        # Wait for sync
        self.connected()
        
        while self.is_running:
            if not self.mumble.is_alive():
                logger.error("EchoBot: Mumble thread died. Initiating container restart via sys.exit...")
                # In Docker, we just exit and let the supervisor handle it.
                sys.exit(1)
            time.sleep(1)

if __name__ == "__main__":
    host = os.getenv("MUMBLE_HOST", "murmur")
    port = int(os.getenv("MUMBLE_PORT", 64738))
    name = os.getenv("BOT_NAME", "EchoBot")
    cert = os.getenv("BOT_CERT", "/bots/certs/echo.pem")
    
    bot = EchoBot(host, port, name, certfile=cert)
    bot.run()
