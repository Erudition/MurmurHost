import asyncio
import os
import sys
import time
import audioop
import datetime
import contextlib
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# --- CONFIGURATION ---
MODEL_ID = "models/gemini-2.5-flash-native-audio-preview-12-2025"
VOICE_NAME = "Fenrir"
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_NAME = "Benny Botman"
API_KEY = os.getenv("GEMINI_API_KEY")

AUDIENCE_CHANNEL = "Audience 👂"
STAGE_CHANNEL = "🎙️ Stage 🔴"
STUDIO_CHANNEL = "Studio 🗣️"
MIC_CHECK_CHANNEL = "Mic Check 🎧"
AI_TEST_ROOM = "AI Test Room"

class MumbleGeminiBot:
    def __init__(self):
        self.api_key = API_KEY
        self.mumble = None
        self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1alpha'})
        self.to_gemini_queue = asyncio.Queue(maxsize=2000)
        self.is_running = True
        self.gemini_session = None
        self.current_speaker = None
        self.total_tokens = 0
        self.sound_counter = 0
        self.total_requests = 0
        self.current_modality = "AUDIO"
        
        # Session Resumption
        self.resumption_token = None
        
        # Stats
        self.dropout_counts = 0
        self.total_retries = 0
        self.successful_retries = 0
        self.total_disconnection_duration = 0
        self.last_disconnect_time = 0
        
        self.sender_task = None
        self.receiver_task = None
        self.gemini_session_ctx = None
        
        # If timed out due to inactivity, wait for audio before reconnecting
        self.waiting_for_activity = False
        self.last_audio_received = 0
        
        # Transcription logging to file
        self.transcript_file = open("/bots/recordings/benny_transcripts.txt", "a")
        
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
        import collections
        self.audio_buffer = collections.deque(maxlen=100) # Buffer approx 2 sec (100 * 20ms)
        
        # Initial Move to AI Test Room (if exists) or Audience (as per spec)
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

    async def connect_live_api(self, modality):
        self.log(f"Connecting to Gemini Live API (Modality: {modality})...")
        
        tools = [
            {"function_declarations": [
                {
                    "name": "mute_self",
                    "description": "Mute the bot's own microphone. Use this when finished speaking or when the conversation should be private.",
                },
                {
                    "name": "unmute_self",
                    "description": "Unmute the bot's own microphone. Use this to start speaking or responding to users.",
                },
                {
                    "name": "change_room",
                    "description": "Move to a different Mumble channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "The name of the channel to move to."}
                        },
                        "required": ["channel_name"]
                    }
                },
                {
                    "name": "send_room_message",
                    "description": "Send a text message to the current room.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "The text message to send."}
                        },
                        "required": ["message"]
                    }
                },
                {
                    "name": "send_direct_message",
                    "description": "Send a private text message to a specific user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "The name of the user to message."},
                            "message": {"type": "string", "description": "The text message to send."}
                        },
                        "required": ["username", "message"]
                    }
                }
            ]}
        ]

        try:
            # Clean up old session/tasks if any
            if self.sender_task: self.sender_task.cancel()
            if self.receiver_task: self.receiver_task.cancel()
            
            # Latest SDK prefers flattened config directly in connect or config object
            # response_modalities should be a list
            config = {
                "response_modalities": [modality],
                "system_instruction": "You are a helpful podcast assistant named Benny Botman.",
                "tools": tools,
            }
            
            # Always include AUDIO config for stability
            config.update({
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": VOICE_NAME}}
                },
                "output_audio_transcription": {},
                "input_audio_transcription": {},
                "enable_affective_dialog": True,
            })

            if self.resumption_token:
                config["session_resumption"] = types.SessionResumptionConfig(handle=self.resumption_token)

            self.log(f"DEBUG: Gemini Config: {config}")
            self.gemini_session_ctx = self.client.aio.live.connect(model=MODEL_ID, config=config)
            self.log(f"Gemini Connect call initiated (Modality: {modality})...")
            self.gemini_session = await self.gemini_session_ctx.__aenter__()
            self.current_modality = modality
            self.log("Gemini Session Ready.")
            
            try:
                chan = self.mumble.channels.get(self.mumble.users.myself['channel_id'])
                chan.send_text_message("<b>Gemini Connected!</b>")
            except: pass
            
            # flush audio buffer
            if hasattr(self, 'audio_buffer') and self.audio_buffer:
                self.log(f"Flushing {len(self.audio_buffer)} buffered audio packets...")
                while self.audio_buffer:
                    pkt = self.audio_buffer.popleft()
                    self.to_gemini_queue.put_nowait(pkt)
            
            # Start tasks
            self.sender_task = asyncio.create_task(self.sender_loop())
            self.receiver_task = asyncio.create_task(self.receiver_loop())
            
        except Exception as e:
            self.log(f"Gemini Connect Failed: {e}")
            await asyncio.sleep(5)
            
    async def disconnect_live_api(self):
        if self.gemini_session_ctx:
            await self.gemini_session_ctx.__aexit__(None, None, None)
        self.gemini_session = None
        if hasattr(self, 'sender_task'): self.sender_task.cancel()
        if hasattr(self, 'receiver_task'): self.receiver_task.cancel()

    async def sender_loop(self):
        self.log("sender_loop started")
        try:
            while self.is_running:
                try:
                    # Wait for items with a 4.0s timeout to allow for keep-alive pings (more frequent than 10s)
                    item = await asyncio.wait_for(self.to_gemini_queue.get(), timeout=4.0)
                except asyncio.TimeoutError:
                    if self.gemini_session:
                        # Don't send keep-alive if we are currently outputting audio (speaking)
                        if hasattr(self, '_speaking') and self._speaking:
                            continue

                        # self.log("DEBUG: Sending keep-alive silence...")
                        # Small 100ms silence packet
                        silence = b'\x00' * 3200 
                        await self.gemini_session.send_realtime_input(
                            media=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
                        )
                    continue

                if self.gemini_session:
                    if isinstance(item, bytes):
                        try:
                            await self.gemini_session.send_realtime_input(
                                media=types.Blob(data=item, mime_type="audio/pcm;rate=16000")
                            )
                        except Exception as e:
                            self.log(f"ERROR: send_realtime_input Failed: {e}")
                            self.gemini_session = None
                    elif isinstance(item, str):
                        try:
                            await self.gemini_session.send_client_content(
                                turns=[types.Content(parts=[types.Part(text=item)], role="user")],
                                turn_complete=False
                            )
                        except Exception as e:
                            self.log(f"ERROR: send_client_content Failed: {e}")
                            self.gemini_session = None
        except asyncio.CancelledError: pass
        except Exception as e:
            self.log(f"!!! SENDER ERROR: {e} !!!")
            self.gemini_session = None
            self.handle_disconnect()

    async def receiver_loop(self):
        self.log("receiver_loop started")
        try:
            async for msg in self.gemini_session.receive():
                # Log all message types for debugging
                # self.log(f"RECV: {msg}") # Too spammy
                if msg.server_content:
                    # print(f"DEBUG_ATTRS: {dir(msg.server_content)}")
                     pass
                # Usage Tracking
                if msg.usage_metadata:
                    self.total_tokens = msg.usage_metadata.total_token_count
                    self.update_comment()
                
                # Input Transcription (Logs) - not all messages have this attribute
                if msg.server_content and hasattr(msg.server_content, 'input_transcription') and msg.server_content.input_transcription:
                    text = msg.server_content.input_transcription.text
                    if text:
                        self.log_transcript("INPUT", text)

                # Output Transcription (Logs)
                if msg.server_content and hasattr(msg.server_content, 'output_transcription') and msg.server_content.output_transcription:
                     text = msg.server_content.output_transcription.text
                     if text:
                         self.log_transcript("OUTPUT", text)
                
                 # Model Turn
                if msg.server_content and hasattr(msg.server_content, 'model_turn') and msg.server_content.model_turn:
                    parts = msg.server_content.model_turn.parts
                    for part in parts:
                        if part.text:
                            # CRITICAL: LOG THIS
                            self.log(f"[TRANSCRIPT MODEL REAL] {part.text}")
                            if self.current_modality == "TEXT":
                                # Send to channel
                                chan = self.mumble.channels.get(self.mumble.users.myself['channel_id'])
                                chan.send_text_message(f"<b>Gemini:</b> {part.text}")
                        if part.inline_data:
                            # Only play audio if we have permission to speak
                            if self.mumble.users.myself.get('mute') or self.mumble.users.myself.get('self_mute'):
                                pass
                            else:
                                pcm_len = len(part.inline_data.data)
                                if pcm_len > 0:
                                    if not hasattr(self, '_speaking') or not self._speaking:
                                        self._speaking = True
                                        self.log(">>> SPEAKING START <<<")
                                    pcm = audioop.ratecv(part.inline_data.data, 2, 1, 24000, 48000, None)[0]
                                    self.mumble.sound_output.add_sound(pcm)

                # Detect end of speaking based on turn_complete
                if msg.tool_call:
                    for call in msg.tool_call.function_calls:
                        await self.handle_tool_call(call)
                
                # Resumption Token
                if msg.session_resumption_update:
                    self.resumption_token = msg.session_resumption_update.handle
                
                if msg.server_content and msg.server_content.turn_complete:
                     self.total_requests += 1
                     self.update_comment()
                     
                     # Mark end of speaking
                     if hasattr(self, '_speaking') and self._speaking:
                         self._speaking = False
                         self.log(">>> SPEAKING END <<<")
                     
                     self.log("Turn Complete")

        except asyncio.CancelledError: pass
        except Exception as e:
            self.log(f"!!! RECEIVER ERROR: {e} !!!")
            self.gemini_session = None
            self.handle_disconnect()

    def handle_disconnect(self):
        self.dropout_counts += 1
        self.last_disconnect_time = time.time()
        self.waiting_for_activity = True
        self.log("Session ended. Waiting for audio activity before reconnecting...")

    async def handle_tool_call(self, call):
        name = call.name
        args = call.args
        id = call.id
        self.log(f"Tool Call: {name}({args})")
        
        result = "Success"
        try:
            if name == "mute_self":
                self.mumble.users.myself.mute()
            elif name == "unmute_self":
                self.mumble.users.myself.unmute()
            elif name == "change_room":
                target = self.mumble.channels.find_by_name(args["channel_name"])
                if target:
                    self.mumble.channels[target["channel_id"]].move_in()
                else:
                    result = f"Error: Channel {args['channel_name']} not found."
            elif name == "send_room_message":
                chan = self.mumble.channels.get(self.mumble.users.myself['channel_id'])
                chan.send_text_message(f"<b>{BOT_NAME}:</b> {args['message']}")
            elif name == "send_direct_message":
                target_user = None
                for u in self.mumble.users.values():
                    if u['name'] == args['username']:
                        target_user = u
                        break
                if target_user:
                    target_user.send_text_message(f"<b>(Private) {BOT_NAME}:</b> {args['message']}")
                else:
                    result = f"Error: User {args['username']} not found."
        except Exception as e:
            result = f"Error: {e}"

        # Send tool response
        if self.gemini_session:
            await self.gemini_session.send(input=types.LiveClientToolResponse(
                function_responses=[types.LiveClientFunctionResponse(
                    name=name, id=id, response={"result": result}
                )]
            ))

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
                    import collections
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
                # In this server, Stage is mainly where we speak. 
                # Audience and Backstage are usually suppressed/muted for bots?
                # Actually, spec says: "Whenever in a room with permission to speak"
                
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
                # Benny can be in: Studio subrooms OR Hallway descendants
                # Studio subrooms: Audience, Backstage, Stage (NOT Mic Check)
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

                    # Shall never join a room with Echo Bot (Mic Check)
                    if my_chan['name'] == MIC_CHECK_CHANNEL:
                        self.log("Spec Violation: Benny in Mic Check with Echo! Moving to Audience...")
                        target = self.mumble.channels.find_by_name(AUDIENCE_CHANNEL)
                        if target:
                            self.mumble.users.myself.move_in(target['channel_id'])
                    
                    # If outside the Studio system AND not in a test room AND not in Hallway, move to Audience
                    elif my_chan['name'] not in studio_system and not my_chan['name'].startswith("AI Test") and not is_in_hallway:
                         target = self.mumble.channels.find_by_name(AUDIENCE_CHANNEL)
                         if target:
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
