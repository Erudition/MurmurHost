import os
import time
import struct
import collections
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
from pymumble_py3.soundqueue import SoundQueue

# Re-use WebVTT logic from custom module
from mumblerecbot.webvtt import WebVtt

# --- OGG/OPUS MUXER (Bit-Perfect Wrapper) ---

import binascii

def ogg_crc(data):
    """
    CRITICAL LEARNING: Ogg CRC-32 is non-reflected and uses 0x04c11db7.
    Initial zero-checksum files were rejected by many players. 
    This custom table-based implementation provides valid Ogg page checksums.
    """
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
    """Creates a standard Ogg Page with segments and correct CRC."""
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
    # Inject CRC into the header (offset 22)
    full_page = full_page[:22] + struct.pack("<I", crc) + full_page[26:]
    return full_page

# A valid 20ms Opus silence packet (Config 1, Mono, 48kHz). Only 1 byte!
OPUS_SILENCE_PACKET = b"\x04" 

class OggOpusWriter:
    """
    SOLVE SYNC GAPS (THE 'SOLID TRACK' APPROACH):
    Mumble only sends data when people speak. If we just write packets to disk, 
    tracks will drift apart immediately.
    
    FIX: Every packet is aligned to a 'Wall Clock' relative to session start.
    If a user is silent, we fill the gap with tiny 1-byte Opus silence packets.
    This ensures that dragging files into Audacity results in PERFECT ALIGNMENT.
    """
    def __init__(self, filename, serial, session_start_time):
        self.filename = filename
        self.serial = serial
        self.start_time = session_start_time
        self.page_seq = 0
        self.last_granule = 0
        self.file = open(filename, "wb")
        self._write_headers()

    def _write_headers(self):
        # 1. OpusHead (The required Ogg identification header)
        opus_head = struct.pack("<8sBBHIHB", b"OpusHead", 1, 1, 0, 48000, 0, 0)
        self.file.write(create_ogg_page(0x02, 0, self.serial, self.page_seq, [opus_head]))
        self.page_seq += 1

        # 2. OpusTags (Metadata header, kept minimal)
        opus_tags = struct.pack("<8sII", b"OpusTags", 0, 0)
        self.file.write(create_ogg_page(0x00, 0, self.serial, self.page_seq, [opus_tags]))
        self.page_seq += 1

    def write_packet(self, data, packet_time):
        """Write a voice packet and fill any gap before it with silence."""
        # CLOCK GATE LEARNING: 
        # Discard packets from before the recording started (buffer carry-over).
        if packet_time < self.start_time:
            return

        target_granule = int((packet_time - self.start_time) * 48000)
        
        # Fill gap with 20ms silence packets (960 samples per 48kHz frame)
        while self.last_granule + 960 <= target_granule:
            self.last_granule += 960
            self.file.write(create_ogg_page(0x00, self.last_granule, self.serial, self.page_seq, [OPUS_SILENCE_PACKET]))
            self.page_seq += 1
            
        # Write the actual voice packet (exactly as received, NO RE-ENCODING)
        self.last_granule += 960
        self.file.write(create_ogg_page(0x00, self.last_granule, self.serial, self.page_seq, [data]))
        self.page_seq += 1

    def finalize(self, end_time):
        """Append silence until the exact moment the session stopped to keep tracks same length."""
        target_granule = int((end_time - self.start_time) * 48000)
        while self.last_granule + 960 <= target_granule:
            self.last_granule += 960
            self.file.write(create_ogg_page(0x00, self.last_granule, self.serial, self.page_seq, [OPUS_SILENCE_PACKET]))
            self.page_seq += 1
        self.file.close()

# --- THE MONKEY PATCH ---
# We intercept the sound queue to get raw Opus packets and arrival timestamps.
original_sound_queue_add = SoundQueue.add
def patched_sound_queue_add(self, audio, sequence, type, target):
    if not hasattr(self, 'raw_packets'):
        self.raw_packets = collections.deque()
    if type == 4: # Opus
        self.raw_packets.append({
            'data': audio,
            'time': time.time() # Accurate wall-clock marking
        })
    return original_sound_queue_add(self, audio, sequence, type, target)
SoundQueue.add = patched_sound_queue_add

# --- RECORDER BOT ---

class OpusRecorderBot:
    """
    A passive Mumble recorder that captures individual user tracks to .opus Ogg files.
    - Automated start/stop on launch/shutdown.
    - Absolute wall-clock sync for Audacity compatibility.
    - Real-time bitrate monitoring.
    """
    def __init__(self, host, port, user, password, channel_name):
        self.recording = False
        self.writers = {} 
        self.vtt = None
        self.record_dir = "recordings/"
        os.makedirs(self.record_dir, exist_ok=True)
        self.host = host
        self.port = port
        self.user = user
        self.channel_name = channel_name
        self.start_time = 0
        self.user_stats = {} 

        self.mumble = pymumble.Mumble(host, user, port=port, password=password, reconnect=True)
        self.mumble.set_receive_sound(True)
        
        # Register Persistence Callbacks
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_DISCONNECTED, self.stop_recording)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.message_received)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_USERCREATED, self.user_created)
        
        self.mumble.start()
        self.mumble.is_ready()
        self.connected()

    def connected(self):
        """Handles joining the target room and starting the recording session."""
        try:
            target = self.mumble.channels.find_by_name(self.channel_name)
            if target:
                self.mumble.channels[target['channel_id']].move_in()
                print(f">>> Recorder: Moved to {self.channel_name}")
        except: pass

        if not self.recording:
            self.start_recording()

    def user_created(self, user):
        if self.recording and self.vtt:
             self.vtt.add_cue(f"<c.system>User {user['name']} joined.")

    def message_received(self, message):
        """Supports manual overrides via text commands."""
        text = message.message.strip()
        if text == "/start": self.start_recording()
        elif text == "/stop": self.stop_recording()
        elif text == "/newfile":
            self.stop_recording()
            self.start_recording()

    def update_comment(self):
        """Provides live bitrate and session info in the Bot's comment."""
        if not self.recording:
            self.mumble.users.myself.comment("Recording IDLE")
            return
        
        comment = f"<b>Recording ACTIVE</b><br/>"
        comment += f"Session: <code>{self.session_prefix}</code><br/>"
        comment += "<hr/>"
        for session, stats in self.user_stats.items():
            user = self.mumble.users.get(session)
            if user:
                if stats['packets'] > 0:
                    bitrate = (stats['bytes'] * 8) / (stats['packets'] * 0.02) / 1000
                    comment += f"• {user['name']}: {bitrate:.1f} kbps<br/>"
        self.mumble.users.myself.comment(comment)

    def start_recording(self):
        """Initializes a new recording session."""
        if self.recording: return
        self.recording = True
        
        # BUFFER PURGE LEARNING: 
        # Clear any audio that was heard while idling to prevent 'ghost voice' overlaps at the start.
        for user in self.mumble.users.values():
            if hasattr(user.sound, 'raw_packets'):
                user.sound.raw_packets.clear()

        self.start_time = time.time()
        
        import datetime
        now = datetime.datetime.now()
        if now.hour < 7:
            # Use yesterday's date if we are in the 'late night' block
            display_date = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
        else:
            display_date = now.strftime("%Y%m%d")
        
        timestamp = now.strftime("%H%M%S")
        self.session_prefix = f"podcast-{display_date}-{timestamp}"
        self.user_stats = {}
        self.vtt = WebVtt(os.path.join(self.record_dir, f"{self.session_prefix}.vtt"))
        self.vtt.add_cue("<c.system>Recording started.")
        self.mumble.users.myself.recording() # Show the recording icon for transparency
        self.update_comment()

    def stop_recording(self, *args):
        """Safely stops recording and finalizes all files."""
        if not self.recording: return
        now = time.time()
        duration_sec = int(now - self.start_time)
        duration_str = f"{duration_sec // 60:02d}:{duration_sec % 60:02d}"
        
        print(f"Stopping recording... Duration: {duration_str}")
        self.recording = False
        self.mumble.users.myself.unrecording()
        self.update_comment()
        
        if self.vtt:
            self.vtt.add_cue(f"<c.system>Recording stopped. Duration: {duration_str}")
            # Explicit close/flush is vital for transcript integrity.
            self.vtt.close()
            self.vtt = None
        
        # Finalize all tracks with silence until the end so files are identical lengths.
        for writer in self.writers.values():
            writer.finalize(now)
        self.writers = {}

    def run(self):
        """Main Audio Capture Loop."""
        last_comment_update = 0
        active_captions = {} 
        try:
            while self.mumble.is_alive():
                if self.recording:
                    changed = False
                    for user in list(self.mumble.users.values()):
                        session = user['session']
                        queue = user.sound
                        
                        # SKIP SELF: Prevents the bot from recording its own silence.
                        if session == self.mumble.users.myself['session']:
                            continue

                        # Handle transcript captions (Who is speaking now)
                        if queue.is_sound():
                            if self.vtt and session not in active_captions:
                                active_captions[session] = self.vtt.add_cue(f"<v {user['name']}>{user['name']}")
                        else:
                            if session in active_captions:
                                active_captions[session].end()
                                del active_captions[session]

                        # Handle audio packets
                        if hasattr(queue, 'raw_packets') and queue.raw_packets:
                            if session not in self.writers:
                                # LAZY TRACKS: Tracks are only created when someone FIRST speaks,
                                # preventing the folder from filling with empty files for idle users.
                                filename = os.path.join(self.record_dir, f"{self.session_prefix}-{user['name']}.opus")
                                self.writers[session] = OggOpusWriter(filename, session, self.start_time)
                                self.user_stats[session] = {'packets': 0, 'bytes': 0, 'filename': filename}
                                print(f"Started solid track for {user['name']}")
                                changed = True
                            
                            while queue.raw_packets:
                                packet = queue.raw_packets.popleft()
                                self.writers[session].write_packet(packet['data'], packet['time'])
                                self.user_stats[session]['packets'] += 1
                                self.user_stats[session]['bytes'] += len(packet['data'])
                    
                    if changed or (time.time() - last_comment_update > 5):
                        self.update_comment()
                        last_comment_update = time.time()
                else:
                    if active_captions:
                        for cue in active_captions.values(): cue.end()
                        active_captions = {}
                time.sleep(0.01)
        finally:
            # SHUTDOWN LEARNING: Guarantee finalize on crash or kick.
            self.stop_recording()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--user", default="OpusRecorder")
    parser.add_argument("--channel", default="Root")
    args = parser.parse_args()
    bot = OpusRecorderBot(args.host, 64738, args.user, "", args.channel)
    bot.run()
