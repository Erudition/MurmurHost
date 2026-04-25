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
        
        # Parrot Mode State
        self.verified_users = set()
        self.first_sound_times = {} # {username: timestamp}
        self.audio_buffers = {}     # username -> bytearray
        self.last_audio_times = {}  # username -> float
        self.is_parroting = {}      # username -> bool

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
        
        # Move to Mic Check channel
        mic_check = os.getenv("MIC_CHECK_CHANNEL", "Mic Check 🎧")
        try:
            target = self.mumble.channels.find_by_name(mic_check)
            if target:
                logger.info(f"EchoBot: Moving to {mic_check}...")
                self.mumble.users.myself.move_in(target['channel_id'])
            else:
                logger.warning(f"EchoBot: Channel '{mic_check}' not found.")
        except Exception as e:
            logger.error(f"EchoBot Move Error: {e}")

    def sound_received(self, user, sound):
        try:
            username = user.get('name')
            if not username or username == self._name: return
            
            # 1. INTERRUPTION: If user speaks while we are parroting, kill the output
            if self.is_parroting.get(username):
                logger.debug(f"EchoBot: Interrupted by {username}. Clearing buffer.")
                self.mumble.sound_output.clear_buffer()
                self.is_parroting[username] = False
                if username in self.audio_buffers:
                    self.audio_buffers[username] = bytearray()

            # 2. MODE HANDLING
            if username in self.verified_users:
                # PARROT: Buffer audio
                if username not in self.audio_buffers:
                    self.audio_buffers[username] = bytearray()
                self.audio_buffers[username].extend(sound.pcm)
                self.last_audio_times[username] = time.time()
            else:
                # ECHO: Instant loopback for unverified users
                self.mumble.sound_output.add_sound(sound.pcm)
            
            # 3. VERIFICATION Transition
            if username not in self.verified_users:
                if username not in self.first_sound_times:
                    self.first_sound_times[username] = time.time()
                elif time.time() - self.first_sound_times[username] > 3.0:
                    logger.info(f"EchoBot: Verifying {username}...")
                    self.verified_users.add(username)
                    user.send_text_message("Mic Checked - I can hear you! Switching to Parrot Mode.")
                    self.notify_supervisor(username)
                    
        except Exception as e:
            logger.error(f"EchoBot Callback Error: {e}")

    def notify_supervisor(self, username):
        supervisor = None
        for u in self.mumble.users.values():
            if u.get('name') == "Supervisor":
                supervisor = u
                break
        
        if supervisor:
            supervisor.send_text_message(f"!verify_user {username}")
        else:
            logger.warning("EchoBot: Supervisor not found to notify.")

    def run(self):
        self.connect()
        # Wait for sync
        self.connected()
        
        while self.is_running:
            if not self.mumble.is_alive():
                logger.error("EchoBot: Mumble thread died. Initiating container restart via sys.exit...")
                sys.exit(1)
            
            # Parrot Trigger Logic (80ms silence detection)
            now = time.time()
            for name in list(self.last_audio_times.keys()):
                if name in self.audio_buffers and len(self.audio_buffers[name]) > 0:
                    # If silence threshold reached and not currently marked as parroting
                    if now - self.last_audio_times[name] > 0.08:
                        logger.info(f"EchoBot: Parrotting {len(self.audio_buffers[name])} bytes to {name}")
                        self.mumble.sound_output.add_sound(bytes(self.audio_buffers[name]))
                        self.audio_buffers[name] = bytearray()
                        self.is_parroting[name] = True
            
            # Check if playback finished (to reset is_parroting)
            if (hasattr(self.mumble, 'sound_output') and 
                self.mumble.sound_output and 
                self.mumble.sound_output.get_buffer_size() == 0):
                for name in self.is_parroting:
                    self.is_parroting[name] = False

            time.sleep(0.01) # 10ms resolution for snappy VAD

if __name__ == "__main__":
    host = os.getenv("MUMBLE_HOST", "murmur")
    port = int(os.getenv("MUMBLE_PORT", 64738))
    name = os.getenv("BOT_NAME", "EchoBot")
    cert = os.getenv("BOT_CERT", "/bots/certs/echo.pem")
    key = os.getenv("BOT_KEY", "/bots/certs/echo_key.pem")
    
    bot = EchoBot(host, port, name, certfile=cert, keyfile=key)
    bot.run()
