import asyncio
import os
import sys
import time
import audioop
import datetime
import contextlib
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
import collections

# Import extracted integration
from gemini_live_integration import GeminiLiveIntegration

# --- CONFIGURATION ---
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_NAME = "Benny Botman"

AUDIENCE_CHANNEL = "Audience 👂"
STAGE_CHANNEL = "🎙️ Stage 🔴"
STUDIO_CHANNEL = "Studio 🗣️"
MIC_CHECK_CHANNEL = "Mic Check 🎧"
AI_TEST_ROOM = "AI Test Room"

class MumbleGeminiBot(GeminiLiveIntegration):
    def __init__(self):
        super().__init__()
        self.mumble = None
        self.is_running = True
        self.current_speaker = None
        self.sound_counter = 0
        
        # Stats
        self.dropout_counts = 0
        self.total_retries = 0
        self.successful_retries = 0
        self.total_disconnection_duration = 0
        self.last_disconnect_time = 0
        
        # If timed out due to inactivity, wait for audio before reconnecting
        self.waiting_for_activity = False
        self.last_audio_received = 0
        
        # Transcription logging to file
        self.transcript_file = open("/bots/recordings/benny_transcripts.txt", "a")
        
        # For integration methods that might use it
        self.bot_name = BOT_NAME
        
    def log_transcript(self, direction, text):
        import datetime
        ts = datetime.datetime.now().isoformat()
        line = f"[{ts}] [{direction}] {text}\n"
        self.transcript_file.write(line)
        self.transcript_file.flush()
        self.log(f"[TRANSCRIPT {direction}] {text}")
        
    def log(self, text):
        print(f"[{BOT_NAME}] {text}", flush=True)

    async def connected(self):
        self.log(f"Connected to Mumble as {self.mumble.users.myself['name']}")
        self.mumble.users.myself.deaf(False)
        self.mumble.users.myself.unmute()
        self.is_connected = True

    async def connect_mumble(self):
        self.log(f"Connecting to Mumble at {MUMBLE_HOST} as {BOT_NAME}...")
        
        # Use persistent certificate for identity
        cert_file = "/bots/certs/benny.pem"
        key_file = "/bots/certs/benny_key.pem"
        
        self.mumble = pymumble.Mumble(MUMBLE_HOST, BOT_NAME, port=64738,
                                       certfile=cert_file, keyfile=key_file)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.text_message_received)
        self.mumble.start()
        
        for _ in range(20):
            if self.mumble.is_ready() and self.mumble.users.myself: break
            await asyncio.sleep(0.5)
            
        if not self.mumble.users.myself:
            raise Exception("Mumble Connection Failed")
            
        self.mumble.set_receive_sound(True)
        
        # Audio Buffer for reconnection
        self.audio_buffer = collections.deque(maxlen=100) # Buffer approx 2 sec (100 * 20ms)
        
        # Initial Move to AI Test Room (if exists) or Audience (as per spec)
        target_chan = None
        try:
             target_chan = self.mumble.channels.find_by_name(AI_TEST_ROOM)
        except: pass
        
        if not target_chan:
            target_chan = self.mumble.channels.find_by_name(AUDIENCE_CHANNEL)
        
        if not target_chan:
             self.log("WARNING: Could not find target channel by name!")
             for c in self.mumble.channels.values():
                 self.log(f"Available Channel: {[c['name']]}")

        if target_chan:
            self.mumble.users.myself.move_in(target_chan['channel_id'])
            self.log(f"Requested move to {target_chan['name']} (ID: {target_chan['channel_id']})")
        else:
            self.log("WARNING: Could not find target channel by name!")
            # Print available channels for debugging
            for c in self.mumble.channels.values():
                self.log(f"Available Channel: {c['name']}")
            
        self.update_comment()

    def update_comment(self):
        # Stats report as per spec
        msg = (f"<b>{BOT_NAME} (Gemini 2.5)</b><br/>"
               f"Usage: {self.total_tokens} / 128,000 tokens<br/>"
               f"Requests: {self.total_requests} / 50<br/>"
               f"Dropouts: {self.dropout_counts}<br/>"
               f"Retries: {self.successful_retries} / {self.total_retries}<br/>"
               f"Offline Duration: {int(self.total_disconnection_duration)}s")
        try:
             self.mumble.users.myself.comment(msg)
        except: pass

    def handle_disconnect(self):
        self.dropout_counts += 1
        self.last_disconnect_time = time.time()
        self.waiting_for_activity = True
        self.log("Session ended. Waiting for audio activity before reconnecting...")

    def sound_received(self, user, sound):
        self.sound_counter += 1
        
        # RMS Calculation for Activity & Interruption
        try:
            pcm_data = sound.pcm
            # Resample from 48000 to 16000 for Gemini
            resampled = audioop.ratecv(pcm_data, 2, 1, 48000, 16000, None)[0]
            rms = audioop.rms(resampled, 2)
            
            # 1. Wake up if waiting for activity
            if self.waiting_for_activity:
                # Buffer the audio so we don't lose the start of the sentence
                if not hasattr(self, 'audio_buffer'):
                    self.audio_buffer = collections.deque(maxlen=100)
                self.audio_buffer.append(resampled)

                if self.sound_counter % 10 == 0:
                     self.log(f"Waiting for activity... RMS: {rms}")
                
                # Lower threshold to 150 to be more sensitive
                if rms > 150: 
                    self.log(f"Audio activity detected (RMS: {rms}) - flagging for reconnection")
                    self.waiting_for_activity = False
                    try:
                        chan = self.mumble.channels.get(self.mumble.users.myself['channel_id'])
                        chan.send_text_message("<i>👂 Waking up...</i>")
                    except: pass
            
            # 2. Interruption Handling
            # If the bot is speaking and the user speaks over it (RMS > Threshold), clear the buffer.
            if hasattr(self, '_speaking') and self._speaking and rms > 500:
                self.log(f"Interruption detected (RMS: {rms}) - Clearing local audio buffer")
                self.mumble.sound_output.clear_buffer()
                # We do NOT return here; we still want to send the user's interruption audio to Gemini
                # so it knows to stop generating/change context.

            if not self.gemini_session: 
                return
            
            name = user.get('name')
            if name != self.current_speaker:
                # self.log(f"DEBUG: Audio received from {name}")
                self.current_speaker = name
            
            # Track activity for reconnection logic (keep-alive watchdog)
            self.last_audio_received = time.time()
            
            # Send everything to Gemini, let its VAD handle it
            self.to_gemini_queue.put_nowait(resampled)

        except Exception as e:
            self.log(f"DEBUG: sound_received error: {e}")

    def text_message_received(self, msg):
        sender = self.mumble.users.get(msg.actor)
        if sender and sender['name'] != BOT_NAME:
            self.log(f"TEXT from {sender['name']}: {msg.message}")
            # Strip HTML tags from Mumble message
            import re
            clean_text = re.sub('<[^<]+?>', '', msg.message).strip()
            
            # Handle test commands
            if clean_text == "!movetest":
                self.log("Received !movetest command, moving to AI Test Room...")
                ai_test = self.mumble.channels.find_by_name("AI Test Room")
                if ai_test:
                    self.mumble.users.myself.move_in(ai_test['channel_id'])
                    self.log(f"Moved to AI Test Room (ID: {ai_test['channel_id']})")
                else:
                    self.log("AI Test Room not found")
                return
            
            self.to_gemini_queue.put_nowait(clean_text)

    async def run(self):
        await self.connect_mumble()
        
        while self.is_running:
            try:
                user = self.mumble.users.myself
                my_chan = self.mumble.channels.get(user['channel_id'])
                
                # Permission Check
                on_stage = (my_chan and my_chan['name'] == STAGE_CHANNEL)
                can_speak = on_stage or (my_chan and my_chan['name'] in [STUDIO_CHANNEL, MIC_CHECK_CHANNEL, AI_TEST_ROOM])
                
                # Check for humans transmitting
                humans_speaking = False
                for u in list(self.mumble.users.values()):
                    if u['name'] != BOT_NAME and u['session'] != user['session']:
                        if u.sound.is_sound():
                            humans_speaking = True
                            break

                is_deafened = user.get('self_deaf', False) or user.get('deaf', False)
                is_muted = user.get('self_mute', False) or user.get('mute', False)
                
                if time.time() % 10 < 1:
                    self.log(f"STATE: OnStage={on_stage} CanSpeak={can_speak} Deaf={is_deafened} Mute={is_muted} Chan={my_chan['name'] if my_chan else 'None'}")
                
                # Room Presence Logic (as per spec)
                studio_system = [STUDIO_CHANNEL, AUDIENCE_CHANNEL, "Backstage 🤐", STAGE_CHANNEL]
                
                # Check occupancy of studio system + Hallway (Recursive)
                studio_occupied = False
                
                # Robust Hallway finder (startswith to handle unicode)
                hallway_root_id = -1
                for c in self.mumble.channels.values():
                    if c.get('name', '').startswith("Hallway"):
                        hallway_root_id = c['channel_id']
                        break

                for u in self.mumble.users.values():
                    if u['name'] not in [BOT_NAME, "Supervisor", "Echo", "Recording"] and u.get('name'):
                        chan = self.mumble.channels.get(u['channel_id'])
                        if not chan: continue
                        
                        # 1. Direct Name Match (Studio System)
                        if chan['name'] in studio_system:
                            studio_occupied = True
                            break
                        
                        # 2. Hallway Hierarchy Check
                        if hallway_root_id != -1:
                            curr = chan
                            while curr:
                                if curr['channel_id'] == hallway_root_id:
                                    studio_occupied = True
                                    break
                                parent_id = curr.get('parent')
                                curr = self.mumble.channels.get(parent_id) if parent_id is not None else None
                            if studio_occupied: break
                
                if not studio_occupied:
                    # Spec: Leaves when Studio (or subrooms) are empty for 30 seconds
                    pass

                # Move Logic
                if my_chan:
                    is_in_hallway = False
                    if hallway_root_id != -1:
                        curr = my_chan
                        while curr:
                            if curr['channel_id'] == hallway_root_id:
                                is_in_hallway = True
                                break
                            parent_id = curr.get('parent')
                            curr = self.mumble.channels.get(parent_id) if parent_id is not None else None

                    # Correct Presence Priority Logic
                    in_studio = my_chan['name'] in studio_system
                    in_test = my_chan['name'].startswith("AI Test")
                    
                    if my_chan['name'] == MIC_CHECK_CHANNEL:
                        self.log("Spec Violation: Benny in Mic Check with Echo! Moving to Audience...")
                        target = self.mumble.channels.find_by_name(AUDIENCE_CHANNEL)
                        if target: self.mumble.users.myself.move_in(target['channel_id'])
                    
                    elif not in_test and not in_studio and not is_in_hallway:
                         target = None
                         try:
                             target = self.mumble.channels.find_by_name(AI_TEST_ROOM)
                         except: pass
                         
                         if not target: 
                             target = self.mumble.channels.find_by_name(AUDIENCE_CHANNEL)
                         
                         if target and target['channel_id'] != my_chan['channel_id']:
                             self.log(f"Auto-Move: {my_chan['name']} is not the target. Moving to {target['name']}...")
                             self.mumble.users.myself.move_in(target['channel_id'])
                        
                # Force undeafen if we want to hear
                if is_deafened:
                    self.log("Forcing UNDEAFEN...")
                    user.undeafen()
                
                if is_deafened:
                    if self.gemini_session:
                        await self.disconnect_live_api()
                else:
                    # ALWAYS use AUDIO mode for Gemini Live API
                    modality = "AUDIO"
                    
                    if not self.gemini_session and not self.waiting_for_activity:
                        self.log("Initializing Gemini Live Session...")
                        await self.connect_live_api(modality)
                
                await asyncio.sleep(1)
            except Exception as e:
                self.log(f"Loop Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    bot = MumbleGeminiBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        pass
