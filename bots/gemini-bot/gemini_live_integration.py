import asyncio
import os
import time
import audioop
import collections
import contextlib
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import tools

# --- CONFIGURATION ---
MODEL_ID = "models/gemini-2.5-flash-native-audio-preview-12-2025"
VOICE_NAME = "Fenrir"
API_KEY = os.getenv("GEMINI_API_KEY")

class GeminiLiveIntegration:
    def __init__(self):
        self.api_key = API_KEY
        self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1beta'})
        self.to_gemini_queue = asyncio.Queue(maxsize=2000)
        self.gemini_session = None
        self.total_tokens = 0
        self.total_requests = 0
        self.current_modality = "AUDIO"
        self.is_running = True
        self.bot_name = "Benny Botman"
        
        # Session Resumption
        self.resumption_token = None
        
        self.sender_task = None
        self.receiver_task = None
        self.gemini_session_ctx = None
        self._speaking = False
        
        # Audio Handling State (moved from bot.py)
        self.waiting_for_activity = False
        self.last_audio_received = 0
        self.audio_buffer = collections.deque(maxlen=100)  # Buffer approx 2 sec (100 * 20ms)
        self.current_speaker = None
        self.sound_counter = 0
        
        # Stats
        self.dropout_counts = 0
        self.total_retries = 0
        self.successful_retries = 0
        self.total_disconnection_duration = 0
        self.last_disconnect_time = 0

    def get_system_prompt(self):
        prompt_path = os.path.join(os.path.dirname(__file__), "SYSTEM_PROMPT.md")
        try:
            with open(prompt_path, "r") as f:
                return f.read().strip()
        except Exception as e:
            self.log(f"Warning: Could not read {prompt_path}: {e}. Using default prompt.")
            return "You are a helpful podcast assistant named Benny Botman."

    async def connect_live_api(self, modality):
        self.log(f"Connecting to Gemini Live API (Modality: {modality})...")
        self._speaking = False
        self.current_modality = modality
        
        # Drain queues to ensure clean state on reconnect
        while not self.to_gemini_queue.empty():
            try: self.to_gemini_queue.get_nowait()
            except: break
        
        tools_def = tools.get_tools_definition()

        try:
            # Fake session to keep bot.py sending audio to to_gemini_queue during connection
            self.gemini_session = "CONNECTING"
            
            # Clean up old session/tasks if any
            if self.sender_task: 
                self.sender_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.sender_task
            if self.receiver_task: 
                self.receiver_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.receiver_task
            
            # Spec: set contextWindowCompression config to use types.SlidingWindow()
            # Spec: configure the sessionResumption field to smoothly handle WebSocket resets
            config = types.LiveConnectConfig(
                response_modalities=[modality],
                system_instruction=types.Content(parts=[types.Part(text=self.get_system_prompt())]),
                tools=tools_def, 
                context_window_compression=types.ContextWindowCompressionConfig(
                    sliding_window=types.SlidingWindow()
                ),
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
                    )
                ),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                input_audio_transcription=types.AudioTranscriptionConfig(),
            )

            # if self.resumption_token:
            #     config.session_resumption = types.SessionResumptionConfig(handle=self.resumption_token)
            # else:
            #      # Enable resumption for future sessions by including the config
            #      config.session_resumption = types.SessionResumptionConfig()
            
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
            if self.sender_task:
                 self.sender_task.cancel()
            if self.receiver_task:
                 self.receiver_task.cancel()
                 
            self.sender_task = asyncio.create_task(self.sender_loop())
            self.receiver_task = asyncio.create_task(self.receiver_loop())
            
            # Re-register sound callback to ensure audio flow
            if hasattr(self, 'mumble') and hasattr(self.mumble, 'callbacks') and hasattr(self, 'sound_received'):
                from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED
                self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
                self.log("Re-registered audio callback.")
            
        except Exception as e:
            self.log(f"Gemini Connect Failed: {e}")
            await asyncio.sleep(5)
            
    async def disconnect_live_api(self):
        if self.gemini_session_ctx:
            await self.gemini_session_ctx.__aexit__(None, None, None)
        self.gemini_session = None
        if hasattr(self, 'sender_task') and self.sender_task: self.sender_task.cancel()
        if hasattr(self, 'receiver_task') and self.receiver_task: self.receiver_task.cancel()

    async def sender_loop(self):
        self.log("sender_loop started")
        try:
            while self.is_running:
                try:
                    # Wait for items with a 9.0s timeout to allow for keep-alive pings (longer persistence)
                    item = await asyncio.wait_for(self.to_gemini_queue.get(), timeout=9.0)
                except asyncio.TimeoutError:
                    if self.gemini_session and not isinstance(self.gemini_session, str):
                        # Don't send keep-alive if we are currently outputting audio (speaking)
                        if hasattr(self, '_speaking') and self._speaking:
                            continue

                        self.log("DEBUG: Sending keep-alive silence...")
                        # Small 200ms silence packet (6400 bytes = 3200 samples @ 16kHz)
                        silence = b'\x00' * 6400 
                        try:
                             await self.gemini_session.send_realtime_input(
                                media=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
                            )
                        except Exception as e:
                             self.log(f"WARNING: send_realtime_input KeepAlive Failed: {e}")
                             # Original behavior: set session to None so main loop triggers reconnect
                             self.gemini_session = None
                    continue

                if self.gemini_session and not isinstance(self.gemini_session, str):
                    if isinstance(item, bytes):
                        try:
                            # Log every 100th packet to see flow
                            if self.sound_counter % 100 == 0:
                                self.log(f"DEBUG: sender_loop sending audio ({len(item)} bytes, Session: {self.gemini_session})")
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
                # Verbose log for ALL messages
                self.log(f"RECV TYPE: {type(msg)}")
                if msg.server_content:
                    self.log(f"RECV CONTENT: {msg.server_content}")
                if msg.tool_call:
                    self.log(f"RECV TOOL: {msg.tool_call}")
                if msg.usage_metadata:
                    self.log(f"RECV USAGE: {msg.usage_metadata}")
                
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
                            self.log(f"[TRANSCRIPT MODEL REAL] {part.text}")
                            if self.current_modality == "TEXT":
                                chan = self.mumble.channels.get(self.mumble.users.myself['channel_id'])
                                chan.send_text_message(f"<b>Gemini:</b> {part.text}")
                        if part.inline_data:
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
                    self.log(f"DEBUG: Resumption Update Received: {msg.session_resumption_update}")
                    if hasattr(msg.session_resumption_update, 'new_handle'):
                        token = msg.session_resumption_update.new_handle
                        if token:
                            self.resumption_token = token
                            self.log(f"DEBUG: Saved Resumption Token: {token[:10]}...")
                    elif hasattr(msg.session_resumption_update, 'handle'):
                         token = msg.session_resumption_update.handle
                         if token:
                             self.resumption_token = token
                             self.log(f"DEBUG: Saved Resumption Token: {token[:10]}...")
                
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

    async def handle_tool_call(self, call):
        result = await tools.dispatch_tool_call(self, call)
        # Send tool response
        if self.gemini_session:
            self.log(f"DEBUG: Sending tool response for {call.name} (Result: {result[:50]}...)")
            await self.gemini_session.send(input=types.LiveClientToolResponse(
                function_responses=[types.LiveClientFunctionResponse(
                    name=call.name, id=call.id, response={"result": result}
                )]
            ))

    def handle_disconnect(self):
        """Called when the Gemini session ends. Sets waiting_for_activity to pause reconnection until audio resumes."""
        self.dropout_counts += 1
        self.last_disconnect_time = time.time()
        self.waiting_for_activity = True
        self.log("Session ended. Waiting for audio activity before reconnecting...")

    def sound_received(self, user, sound):
        """
        Core audio reception callback. Resamples Mumble audio (48kHz) to Gemini format (16kHz),
        handles activity detection, interruption, and pushes audio to the Gemini queue.
        """
        self.sound_counter += 1
        
        # Periodic debug log to trace if callback is invoked
        if self.sound_counter % 100 == 0:
            self.log(f"DEBUG: sound_received called {self.sound_counter} times")
        
        try:
            pcm_data = sound.pcm
            # Resample from 48000 to 16000 for Gemini
            resampled = audioop.ratecv(pcm_data, 2, 1, 48000, 16000, None)[0]
            rms = audioop.rms(resampled, 2)
            
            # 1. Wake up if waiting for activity
            if self.waiting_for_activity:
                # Buffer the audio so we don't lose the start of the sentence
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
            
            # 2. Interruption Handling (Disabled for debugging Turn 2 silence)
            # if hasattr(self, '_speaking') and self._speaking and rms > 500:
            #     self.log(f"Interruption detected (RMS: {rms}) - Clearing local audio buffer")
            #     self.mumble.sound_output.clear_buffer()
            
            # 3. Session-loss Buffering
            # If the session is not ready, buffer the audio so we don't lose turns during reconnect.
            if not self.gemini_session:
                if not hasattr(self, 'audio_buffer'):
                    self.audio_buffer = collections.deque(maxlen=100)
                self.audio_buffer.append(resampled)
                return
            
            name = user.get('name')
            if name != self.current_speaker:
                self.current_speaker = name
            
            # Track activity for reconnection logic (keep-alive watchdog)
            self.last_audio_received = time.time()
            
            # Send everything to Gemini, let its VAD handle it
            try:
                self.to_gemini_queue.put_nowait(resampled)
            except Exception as qe:
                self.log(f"DEBUG: Queue put failed: {qe}")

        except Exception as e:
            self.log(f"DEBUG: sound_received error: {e}")
