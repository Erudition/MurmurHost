import os
import logging
import time
import pymumble_py3 as pymumble
from pymumble_py3.constants import *

# Enable debug logging for pymumble diagnostics
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EchoBot")

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
        
        self.mumble = pymumble.Mumble(HOST, USER, port=64738, reconnect=True,
                                       certfile=cert_file, keyfile=key_file)
        
        # IMPORTANT: Set receive_sound BEFORE start() to ensure user sound queues
        # are initialized as soon as they are discovered during sync.
        self.mumble.set_receive_sound(True)
        
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        self.mumble.start()
        
    def connected(self):
        # Wait for full synchronization
        print("EchoBot: Waiting for server synchronization...")
        self.mumble.is_ready() 
        
        has_udp = getattr(self.mumble, 'is_udp', 'unknown')
        if has_udp == 'unknown':
            has_udp = True if getattr(self.mumble, 'udp_socket', None) else False
        print(f"EchoBot: Connected via {'UDP' if has_udp else 'TCP Fallback'}")
        
        print(f"EchoBot: Synchronized as {self.mumble.users.myself.get('name')} (ID: {self.mumble.users.myself.get('session')})")
        
        # Audio is already enabled pre-connection to avoid race conditions.
        try:
            self.mumble.users.myself.unmute()
            self.mumble.users.myself.undeafen()
            print(f"EchoBot State: Muted: {self.mumble.users.myself.get('mute')}, Deafened: {self.mumble.users.myself.get('deaf')}")
        except Exception as e:
            print(f"EchoBot State Error: {e}")
            
        try:
            print(f"EchoBot: Searching for channel '{MIC_CHECK_CHANNEL}'...")
            target = self.mumble.channels.find_by_name(MIC_CHECK_CHANNEL)
            if target:
                print(f"EchoBot: Found channel {target['name']} (ID: {target['channel_id']}). Moving in...")
                self.mumble.channels[target['channel_id']].move_in()
                
                # Check who is here
                time.sleep(2) # Give it more time to sync users
                print("EchoBot: Full user states in channel:")
                for u in self.mumble.users.values():
                    if u['channel_id'] == target['channel_id']:
                        print(f"  - {u['name']}: Muted={u.get('mute')}, Deafened={u.get('deaf')}, SelfMute={u.get('self_mute')}, SelfDeaf={u.get('self_deaf')}, Session={u.get('session')}")
                
                channel_users = [u['name'] for u in self.mumble.users.values() if u['channel_id'] == target['channel_id']]
                print(f"EchoBot: Users currently in channel: {channel_users}")
            else:
                print(f"EchoBot: Channel '{MIC_CHECK_CHANNEL}' NOT FOUND!")
                print(f"Available channels: {[c['name'] for c in self.mumble.channels.values() if 'name' in c]}")
        except Exception as e:
            print(f"EchoBot Move Error: {e}")

    def sound_received(self, user, sound):
        # Entry heartbeat - removed redundant per-frame debug print
        try:
            # DIAGNOSTIC: Log frame receipt
            name = user.get('name', 'Unknown')
            pcm_len = len(sound.pcm) if hasattr(sound, 'pcm') and sound.pcm else 0
            
            # ECHO: Bounce audio back
            if pcm_len > 0:
                self.mumble.sound_output.add_sound(sound.pcm)
            else:
                # Try raw data if pcm is empty
                print(f"EchoBot: Empty PCM from {name}, raw length: {len(sound.data)}")
            
            # VERIFICATION Logic
            if name and name not in self.verified:
                if name not in self.first_sound_times:
                    self.first_sound_times[name] = time.time()
                    print(f"EchoBot: Started hearing {name}...")
                elif time.time() - self.first_sound_times[name] > 3.0:
                    print(f"EchoBot: Verifying {name}...")
                    self.verified.add(name)
                    user.send_text_message("Mic Check - I can hear you!")
                    # Notify Supervisor
                    self.notify_supervisor(name)
                    
        except Exception as e:
            import traceback
            print(f"EchoBot Audio Error: {e}")
            traceback.print_exc()

    def notify_supervisor(self, username):
        supervisor = None
        for u in self.mumble.users.values():
            if u.get('name') == "Supervisor":
                supervisor = u
                break
        
        if supervisor:
            supervisor.send_text_message(f"!verify_user {username}")
        else:
            print("EchoBot: Supervisor not found to notify.")

    def run(self):
        self.connect()
        while self.is_running:
            if not self.mumble.is_alive():
                print("EchoBot: Mumble thread died. Initiating container restart via sys.exit...")
                # In Docker, we just exit and let the supervisor/restart-policy handle it.
                # Trying to self.mumble.start() again on the same object is impossible.
                sys.exit(1)
            time.sleep(1)

if __name__ == "__main__":
    bot = SimpleEchoBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        pass
