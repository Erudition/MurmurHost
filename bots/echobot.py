import time
import subprocess
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
import datetime

# --- STUDIO CONFIGURATION ---
HOST = "murmur"
USER = "Echo"

def get_session_date():
    """
    Returns the 'Broadcast Day' date.
    If it's before 7 AM, we consider it still part of the previous day's session.
    """
    now = datetime.datetime.now()
    if now.hour < 7:
        return (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

# TARGET_CHANNELS: Rooms where we enforce high-quality audio settings.
TARGET_CHANNELS = ["Mic Check 🎧", "🎙️ Stage 🔴", "Backstage 🤐"]
STAGE_CHANNEL_NAME = "🎙️ Stage 🔴"
MIN_BITRATE = 96.0  # kbps threshold for podcast quality.
REMINDER_INTERVAL = 60 # Seconds between nag messages per user.
LEAVE_DELAY = 60 # Grace period before dismissing the recorder when Stage is empty.

# --- RECORDER SPAWN COMMAND ---
# Note: Recorder is spawned as a separate process to keep its Ogg-muxing timing 
# isolated from the Echo bot's processing.
def get_recorder_cmd():
    return [
        "python3", "/bots/opus_recorder.py",
        "--host", "murmur",
        "--user", f"Recording (Session {get_session_date()})",
        "--channel", "Audience 👂"
    ]

class EchoBotAndManager:
    """
    TRIPLE-PURPOSE BOT:
    1. ECHO: Bounces audio back in 'Mic Check' for latency/quality testing.
    2. MANAGER: Automatically spawns/stops the Recorder bot based on 'Stage' occupancy.
    3. COACH: Monitors real-time bitrate of speakers and nags if quality is < 96kbps.
    """
    def __init__(self):
        self.recorder_process = None
        self.empty_since = None
        self.last_reminded = {} # username -> timestamp
        
        print(">>> EchoBot: Connecting to server...")
        # reconnect=True is essential for server stability.
        self.mumble = pymumble.Mumble(HOST, USER, port=64738, reconnect=True)
        
        # PERSISTENCE LEARNING:
        # Pymumble doesn't remember your channel after a kick. 
        # We must use PYMUMBLE_CLBK_CONNECTED to re-enter our room every time.
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        
        self.mumble.start()
        self.mumble.is_ready()
        
        # set_receive_sound(True) must be called for both Echo and Monitoring to work.
        self.mumble.set_receive_sound(True)
        self.mumble.users.myself.comment("Echo Bot & Studio Manager")
        print(">>> EchoBot: Ready and monitoring.")

    def sound_received(self, user, sound):
        """
        ECHO FEATURE: Bounces PCM audio back to the server.
        Uses Mumble.sound_output.add_sound() which is the correct internal buffer.
        """
        self.mumble.sound_output.add_sound(sound.pcm)

    def connected(self):
        """Ensures the bot finds its way home to 'Mic Check' after connection/reconnection."""
        try:
            target = self.mumble.channels.find_by_name("Mic Check 🎧")
            if target: 
                self.mumble.channels[target['channel_id']].move_in()
                print(">>> EchoBot: Moved to Mic Check 🎧")
        except: pass

    def get_stage_count(self):
        """Checks if anyone is currently in the recording Stage."""
        try:
            stage = self.mumble.channels.find_by_name(STAGE_CHANNEL_NAME)
            if not stage: return 0
            
            count = 0
            for user in self.mumble.users.values():
                if user['channel_id'] == stage['channel_id']:
                    count += 1
            return count
        except:
            return 0

    def start_recorder(self):
        """Spawns the recorder bot process if it's not already running."""
        if self.recorder_process is None or self.recorder_process.poll() is not None:
            print(">>> Manager: 🎙️ Stage occupied! Spawning Recorder Bot...")
            self.recorder_process = subprocess.Popen(get_recorder_cmd())
            self.empty_since = None

    def stop_recorder(self):
        """Dismisses the recorder bot process."""
        if self.recorder_process and self.recorder_process.poll() is None:
            print(">>> Manager: 🛑 Stage empty. Dismissing Recorder Bot...")
            self.recorder_process.terminate()
            self.recorder_process = None

    def check_quality(self):
        """
        COACH FEATURE: Monitors bitrates.
        Uses a monkey-patched SoundQueue (see below) to measure ACTUAL network throughput.
        Necessary because Mumble can enforce MAX quality, but not MIN quality.
        """
        now = time.time()
        for user in list(self.mumble.users.values()):
            if user['name'] == USER: continue
            
            # Only monitor specific 'production' areas.
            channel = self.mumble.channels.get(user['channel_id'])
            if not channel or channel['name'] not in TARGET_CHANNELS:
                continue
                
            queue = user.sound
            # Wait for 50 packets (~1 second) to get a stable average.
            if hasattr(queue, 'total_packets') and queue.total_packets >= 50:
                bitrate = (queue.total_bytes * 8) / (queue.total_packets * 0.02) / 1000
                
                if bitrate < MIN_BITRATE:
                    last_warn = self.last_reminded.get(user['name'], 0)
                    if now - last_warn > REMINDER_INTERVAL:
                        user.send_text_message(
                            f"⚠️ <b>Audio Quality Alert</b><br/>"
                            f"Your current bitrate is <b>{bitrate:.1f} kbps</b>. "
                            f"For podcast-quality recording, please set your quality between <b>96-128 kb/s</b> "
                            f"in your Mumble Settings (Audio Output -> Compression)."
                        )
                        self.last_reminded[user['name']] = now
                        
                # Keep the window 'sliding' by resetting every 100 packets.
                if queue.total_packets > 100:
                    queue.total_bytes = 0
                    queue.total_packets = 0

    def run(self):
        """Main Manager loop."""
        while self.mumble.is_alive():
            # 1. Check audio quality of all active participants.
            self.check_quality()
            
            # 2. Automated Recording Trigger.
            stage_count = self.get_stage_count()
            if stage_count > 0:
                self.start_recorder()
            else:
                # 1-MINUTE GRACE PERIOD: 
                # Prevents the recorder from cycling if someone just disconnects/reconnects.
                if self.recorder_process and self.recorder_process.poll() is None:
                    if self.empty_since is None:
                        self.empty_since = time.time()
                    
                    if time.time() - self.empty_since >= LEAVE_DELAY:
                        self.stop_recorder()
                else:
                    self.empty_since = None
            
            time.sleep(1)

# --- BITRATE MEASUREMENT MONKEY PATCH ---
# LEARNING: Pymumble's standard events don't expose raw compressed packet sizes.
# By patching SoundQueue.add, we can tally the length of every inbound Opus packet 
# to calculate exact bandwidth per-user.
from pymumble_py3.soundqueue import SoundQueue
original_add = SoundQueue.add
def patched_add(self, audio, sequence, type, target):
    if type == 4: # Opus (Mumble Codec ID)
        if not hasattr(self, 'total_bytes'):
            self.total_bytes = 0
            self.total_packets = 0
        self.total_bytes += len(audio)
        self.total_packets += 1
    return original_add(self, audio, sequence, type, target)
SoundQueue.add = patched_add

if __name__ == "__main__":
    bot = EchoBotAndManager()
    bot.run()
