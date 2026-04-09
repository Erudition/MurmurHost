import os
import time
import struct
import signal
import sys
import collections
import datetime
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
from pymumble_py3.soundqueue import SoundQueue

from mumblerecbot.webvtt import WebVtt

# Global reference for signal handler
_recorder_instance = None

# --- OGG/OPUS MUXER (Bit-Perfect Wrapper) ---
def ogg_crc(data):
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xffffffff) ^ OGG_CRC_TABLE[((crc >> 24) ^ byte) & 0xff]
    return crc & 0xffffffff

OGG_CRC_TABLE = []
for i in range(256):
    r = i << 24
    for j in range(8):
        if r & 0x80000000:
            r = ((r << 1) ^ 0x04c11db7) & 0xffffffff
        else:
            r = (r << 1) & 0xffffffff
    OGG_CRC_TABLE.append(r)

def create_ogg_page(header_type, granule_pos, bitstream_serial, page_seq, segments):
    segment_table = b""
    for s in segments:
        l = len(s)
        while l >= 255:
            segment_table += b"\xff"
            l -= 255
        segment_table += struct.pack("B", l)
    
    header = bytearray(struct.pack("<4sBBQIIIB", 
        b"OggS", 0, header_type, granule_pos, bitstream_serial, page_seq, 0, len(segment_table)
    ))
    full_page = header + segment_table + b"".join(segments)
    crc = ogg_crc(full_page)
    full_page = full_page[:22] + struct.pack("<I", crc) + full_page[26:]
    return full_page

OPUS_SILENCE_PACKET = b"\x04" 

class OggOpusWriter:
    def __init__(self, filename, serial, session_start_time):
        self.filename = filename
        self.serial = serial
        self.start_time = session_start_time
        self.page_seq = 0
        self.last_granule = 0
        self.file = open(filename, "wb")
        self._write_headers()

    def _write_headers(self):
        opus_head = struct.pack("<8sBBHIHB", b"OpusHead", 1, 1, 0, 48000, 0, 0)
        self.file.write(create_ogg_page(0x02, 0, self.serial, self.page_seq, [opus_head]))
        self.page_seq += 1
        opus_tags = struct.pack("<8sII", b"OpusTags", 0, 0)
        self.file.write(create_ogg_page(0x00, 0, self.serial, self.page_seq, [opus_tags]))
        self.page_seq += 1

    def write_packet(self, data, packet_time):
        if packet_time < self.start_time: return
        target_granule = int((packet_time - self.start_time) * 48000)
        while self.last_granule + 960 <= target_granule:
            self.last_granule += 960
            self.file.write(create_ogg_page(0x00, self.last_granule, self.serial, self.page_seq, [OPUS_SILENCE_PACKET]))
            self.page_seq += 1
        self.last_granule += 960
        self.file.write(create_ogg_page(0x00, self.last_granule, self.serial, self.page_seq, [data]))
        self.page_seq += 1

    def finalize(self, end_time):
        target_granule = int((end_time - self.start_time) * 48000)
        while self.last_granule + 960 <= target_granule:
            self.last_granule += 960
            self.file.write(create_ogg_page(0x00, self.last_granule, self.serial, self.page_seq, [OPUS_SILENCE_PACKET]))
            self.page_seq += 1
        self.file.close()

# --- MONKEY PATCH (captures raw Opus before decoding) ---
original_sound_queue_add = SoundQueue.add
def patched_sound_queue_add(self, audio, sequence, type, target):
    if not hasattr(self, 'raw_packets'):
        self.raw_packets = collections.deque()
        self._first_packet_logged = False
    if type == 4:  # OPUS
        if not self._first_packet_logged:
            self._first_packet_logged = True
            print(f"DEBUG: First raw Opus packet captured (session target={target})")
        self.raw_packets.append({'data': audio, 'time': time.time()})
    return original_sound_queue_add(self, audio, sequence, type, target)
SoundQueue.add = patched_sound_queue_add

def is_ready(mumble):
    """Wait for all users/channels to be discovered so audio queues are ready."""
    return mumble.is_alive() and mumble.users.myself and 'name' in mumble.users.myself

# --- RECORDER UTILS ---

def get_session_date():
    """Broadcast Day Logic: Sessions before 7 AM belong to previous day"""
    now = datetime.datetime.now()
    if now.hour < 7:
        return (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

# --- RECORDER BOT ---

class OpusRecorderBot:
    def __init__(self, host, port, display_name):
        self.recording = False
        self.writers = {} 
        self.vtt = None
        self.record_dir = os.path.join("recordings", f"Session {get_session_date()}")
        os.makedirs(self.record_dir, exist_ok=True)
        
        self.display_name = display_name
        # Ensure it has the date suffix if it's the default name
        if self.display_name == "Recording":
            self.display_name = f"Recording (Session {get_session_date()})"
             
        print(f">>> Recorder starting as: {self.display_name}")

        # Use persistent certificate for identity
        cert_file = "/bots/certs/recording.pem"
        key_file = "/bots/certs/recording_key.pem"

        self.mumble = pymumble.Mumble(host, self.display_name, port=port, reconnect=True,
                                       certfile=cert_file, keyfile=key_file)
        self.mumble.set_receive_sound(True)
        
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received_diagnostic)
        self.channel_name = "Audience 👂" # Default to Audience (hears Stage)
        self.start_time = 0
        self.user_stats = collections.defaultdict(lambda: {'packets': 0, 'bytes': 0})
        self._diag_first_sound = set()  # Track first audio per user for diagnostics
        
        self.mumble.start()
    
    def sound_received_diagnostic(self, user, sound):
        """Diagnostic callback — logs when audio arrives from each user.
        The actual recording uses the monkey-patched SoundQueue.add for raw Opus."""
        session = user['session']
        if session not in self._diag_first_sound:
            self._diag_first_sound.add(session)
            name = user.get('name', f'session-{session}')
            my_channel = self.mumble.users.myself.get('channel_id', '?')
            user_channel = user.get('channel_id', '?')
            same = 'SAME' if my_channel == user_channel else 'LINKED'
            print(f">>> AUDIO DIAG: First decoded audio from {name} (session {session}, channel {user_channel}, {same} channel)")
    
    def connected(self):
        self.session_prefix = time.strftime("%Y-%m-%d")
        print(f">>> Recorder: Connected to server (pymumble uses TCP tunnel for audio).")
        self.mumble.users.myself.unmute()
        self.mumble.users.myself.undeafen()
        start_wait = time.time()
        while not is_ready(self.mumble):
            time.sleep(0.1)
            if time.time() - start_wait > 10:
                print(">>> Recorder: Sync timeout!")
                break
        
        print(f">>> Recorder: Sync complete. Mumble Users: {len(self.mumble.users)}")
        try:
            target = self.mumble.channels.find_by_name(self.channel_name)
            if target:
                self.mumble.channels[target['channel_id']].move_in()
                print(f">>> Recorder: Moved to {self.channel_name}")
        except: pass

        if not self.recording:
            self.start_recording()

    def update_comment(self):
        if not self.recording:
            self.mumble.users.myself.comment("Recording IDLE")
            return
        
        comment = f"<b>Recording ACTIVE</b><br/>Session: <code>{self.session_prefix}</code><br/><hr/>"
        for session, stats in self.user_stats.items():
            user = self.mumble.users.get(session)
            if user and 'name' in user:
                bitrate = (stats['bytes'] * 8) / (max(1, time.time() - self.start_time) * 1024)
                comment += f"• {user['name']}: {bitrate:.1f} kbps<br/>"
        self.mumble.users.myself.comment(comment)

    def start_recording(self):
        if self.recording: return
        self.recording = True
        
        print(">>> Starting Recording Session...")
        self.start_time = time.time()
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        self.session_prefix = f"podcast-{timestamp}"
        
        self.vtt = WebVtt(os.path.join(self.record_dir, f"{self.session_prefix}.vtt"))
        self.vtt.add_cue("<c.system>Recording started.")
        self.mumble.users.myself.recording() 
        self.update_comment()

    def stop_recording(self):
        if not self.recording: return
        now = time.time()
        duration = int(now - self.start_time)
        print(f"Stopping recording... Duration: {duration}s")
        self.recording = False
        self.mumble.users.myself.unrecording()
        
        if self.vtt:
            self.vtt.close()
            self.vtt = None
        
        for writer in self.writers.values():
            writer.finalize(now)
        self.writers = {}
        self.update_comment()

    def run(self):
        last_comment_update = 0
        last_stat_print = 0
        active_captions = {} 
        try:
            while self.mumble.is_alive():
                now = time.time()
                if self.recording:
                    changed = False
                    for user in list(self.mumble.users.values()):
                        session = user['session']
                        if not hasattr(user, 'sound'):
                            print(f"DEBUG: User {user['name']} has NO sound attribute!")
                            continue
                        
                        queue = user.sound
                        if session == self.mumble.users.myself['session']: continue

                        if queue.is_sound():
                            if self.vtt and session not in active_captions:
                                active_captions[session] = self.vtt.add_cue(f"<v {user['name']}>{user['name']}")
                        elif session in active_captions:
                            active_captions[session].end()
                            del active_captions[session]

                        if hasattr(queue, 'raw_packets') and queue.raw_packets:
                            if session not in self.writers:
                                filename = os.path.join(self.record_dir, f"{self.session_prefix}-{user['name']}.opus")
                                self.writers[session] = OggOpusWriter(filename, session, self.start_time)
                                changed = True
                            
                            while queue.raw_packets:
                                packet = queue.raw_packets.popleft()
                                self.writers[session].write_packet(packet['data'], packet['time'])
                                self.user_stats[session]['packets'] += 1
                                self.user_stats[session]['bytes'] += len(packet['data'])
                    
                    if now - last_stat_print > 5:
                        user_count = len(self.mumble.users)
                        sound_attr_count = sum(1 for u in self.mumble.users.values() if hasattr(u, 'sound'))
                        print(f"DEBUG Loop: Recording={self.recording}, Users={user_count}, SoundAttrs={sound_attr_count}")
                        last_stat_print = now
                        
                    if changed or (now - last_comment_update > 5):
                        self.update_comment()
                        last_comment_update = now
                time.sleep(0.01)
        finally:
            self.stop_recording()

def graceful_shutdown(signum, frame):
    """Signal handler for graceful shutdown."""
    global _recorder_instance
    print(f"\n>>> Recorder: Received signal {signum}, shutting down gracefully...")
    if _recorder_instance:
        _recorder_instance.stop_recording()
    sys.exit(0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("MUMBLE_HOST", "murmur"))
    parser.add_argument("--port", type=int, default=64738)
    parser.add_argument("--channel", default="Audience 👂")
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    
    # Use provided name if available, otherwise default
    bot_name = args.name if args.name else f"Recording (Session {get_session_date()})"
    
    bot = OpusRecorderBot(args.host, args.port, bot_name)
    _recorder_instance = bot  # Set global reference for signal handler
    bot.run()
