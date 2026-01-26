import os
import time
import struct
import collections
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
from pymumble_py3.soundqueue import SoundQueue, SoundChunk

# Re-use WebVTT logic from existing bot
from mumblerecbot.webvtt import WebVtt

# Bitstream constants for Ogg/Opus
OGG_ID_PAGE = b"OggS"
OPUS_HEAD = b"OpusHead"
OPUS_TAGS = b"OpusTags"

def create_ogg_page(header_type, granule_pos, bitstream_serial, page_seq, segments):
    """Creates a basic Ogg page."""
    # Ogg Header: https://xiph.org/ogg/doc/framing.html
    segment_table = b""
    for s in segments:
        l = len(s)
        while l >= 255:
            segment_table += b"\xff"
            l -= 255
        segment_table += struct.pack("B", l)
    
    header = struct.pack("<4sBBQIIIB", 
        OGG_ID_PAGE, 
        0, 
        header_type, 
        granule_pos, 
        bitstream_serial, 
        page_seq, 
        0, # Checksum placeholder
        len(segment_table)
    )
    
    page = header + segment_table + b"".join(segments)
    # Most players handle 0 checksums. Standard CRC is omitted for simplicity in this implementation.
    return page

class OggOpusWriter:
    def __init__(self, filename, serial):
        self.filename = filename
        self.serial = serial
        self.page_seq = 0
        self.granule_pos = 0
        self.file = open(filename, "wb")
        self._write_headers()

    def _write_headers(self):
        # 1. OpusHead
        opus_head = struct.pack("<8sBBHIHB",
            OPUS_HEAD,
            1, # Version
            1, # Channels (mono for multi-track)
            0, # Pre-skip
            48000, # Input sample rate
            0, # Output gain
            0  # Mapping family
        )
        self.file.write(create_ogg_page(0x02, 0, self.serial, self.page_seq, [opus_head]))
        self.page_seq += 1

        # 2. OpusTags
        opus_tags = struct.pack("<8sI", OPUS_TAGS, 0)
        self.file.write(create_ogg_page(0x00, 0, self.serial, self.page_seq, [opus_tags]))
        self.page_seq += 1

    def write_packet(self, data, samples):
        self.granule_pos += samples
        self.file.write(create_ogg_page(0x00, self.granule_pos, self.serial, self.page_seq, [data]))
        self.page_seq += 1

    def close(self):
        self.file.close()

# --- THE MONKEY PATCH ---
original_sound_queue_add = SoundQueue.add

def patched_sound_queue_add(self, audio, sequence, type, target):
    if not hasattr(self, 'raw_packets'):
        self.raw_packets = collections.deque()
    if type == 4: # Opus
        self.raw_packets.append({
            'data': audio,
            'time': time.time()
        })
    return original_sound_queue_add(self, audio, sequence, type, target)

SoundQueue.add = patched_sound_queue_add

# --- RECORDER BOT ---

class OpusRecorderBot:
    def __init__(self, host, port, user, password, channel_name):
        self.recording = False
        self.writers = {} 
        self.vtt = None
        self.record_dir = "recordings/"
        os.makedirs(self.record_dir, exist_ok=True)
        self.host = host
        self.port = port
        self.user = user

        self.mumble = pymumble.Mumble(host, user, port=port, password=password, reconnect=True)
        self.mumble.set_receive_sound(True)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.message_received)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_USERCREATED, self.user_created)
        
        self.mumble.start()
        self.mumble.is_ready()
        
        try:
            target_channel = self.mumble.channels.find_by_name(channel_name)
            if target_channel:
                target_channel.move_in()
        except Exception as e:
            print(f"Warning: Channel '{channel_name}' not found. Remaining in default channel. Error: {e}")

        print(f"Bot connected to {host}:{port} as {user}")

    def user_created(self, user):
        if self.recording and self.vtt:
             self.vtt.add_cue(f"<c.system>User {user['name']} joined.")

    def message_received(self, message):
        text = message.message.strip()
        if text == "/start":
            self.start_recording()
        elif text == "/stop":
            self.stop_recording()
        elif text == "/newfile":
            self.stop_recording()
            self.start_recording()

    def start_recording(self):
        if self.recording: return
        print("Starting recording...")
        self.recording = True
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        self.session_prefix = f"podcast-{timestamp}"
        self.vtt = WebVtt(os.path.join(self.record_dir, f"{self.session_prefix}.vtt"))
        self.vtt.add_cue("<c.system>Recording started.")
        self.mumble.users.myself.recording()
        self.mumble.users.myself.comment("Recording ACTIVE")

    def stop_recording(self):
        if not self.recording: return
        print("Stopping recording...")
        self.recording = False
        self.mumble.users.myself.unrecording()
        self.mumble.users.myself.comment("Recording IDLE")
        if self.vtt:
            self.vtt.add_cue("<c.system>Recording stopped.")
            self.vtt = None
        for writer in self.writers.values():
            writer.close()
        self.writers = {}

    def run(self):
        try:
            while self.mumble.is_alive():
                if self.recording:
                    for user in list(self.mumble.users.values()):
                        session = user['session']
                        queue = user.sound
                        
                        if hasattr(queue, 'raw_packets') and queue.raw_packets:
                            if session not in self.writers:
                                filename = os.path.join(self.record_dir, f"{self.session_prefix}-{user['name']}.opus")
                                self.writers[session] = OggOpusWriter(filename, session)
                                print(f"Started track for {user['name']}")
                            
                            while queue.raw_packets:
                                packet = queue.raw_packets.popleft()
                                # Opus packets at 48kHz, 20ms = 960 samples
                                self.writers[session].write_packet(packet['data'], 960)
                time.sleep(0.01)
        except KeyboardInterrupt:
            self.stop_recording()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=64738)
    parser.add_argument("--user", default="OpusRecorder")
    parser.add_argument("--password", default="")
    parser.add_argument("--channel", default="Root")
    args = parser.parse_args()

    bot = OpusRecorderBot(args.host, args.port, args.user, args.password, args.channel)
    bot.run()
