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
        self.to_gemini_queue = asyncio.Queue(maxsize=100)
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
        self.model_active = False
        
        # Audio Handling State
        self.waiting_for_activity = False
        self.last_audio_received = 0
        self.audio_buffer = collections.deque(maxlen=300)  # Buffer approx 6 sec (300 * 20ms)
        self.current_speaker = None
        self.sound_counter = 0
        self.received_counter = 0 # Track received packets
        self.sent_counter = 0 # Track sent packets
        
        # Stats
        self.dropout_counts = 0
        self.total_retries = 0
        self.successful_retries = 0
        self.total_disconnection_duration = 0
        self.last_disconnect_time = 0
        self.connecting_lock = asyncio.Lock()

    def log(self, text):
        # Default log, likely overridden by subclass
        print(f"[GeminiIntegration] {text}", flush=True)

    def log_transcript(self, direction, text):
        # Default log, likely overridden by subclass
        print(f"[TRANSCRIPT {direction}] {text}", flush=True)

    def update_comment(self):
        # Likely overridden by subclass
        pass

    def get_system_prompt(self):
        prompt_path = os.path.join(os.path.dirname(__file__), "SYSTEM_PROMPT.md")
        try:
            with open(prompt_path, "r") as f:
                return f.read().strip()
        except Exception as e:
            self.log(f"Warning: Could not read {prompt_path}: {e}. Using default prompt.")
            return "You are a helpful podcast assistant named Benny Botman."

    async def connect_live_api(self, modality):
        """
        Connects to the Gemini Live API and starts the sender/receiver tasks.
        """
        if self.connecting_lock.locked():
            self.log("DEBUG: Connection already in progress, skipping.")
            return

        async with self.connecting_lock:
            self.log(f"Connecting to Gemini Live API (Modality: {modality})...")
            self._speaking = False
            self.model_active = False
            self.current_modality = modality
            
            # 0. Prep tools
            tools_def = tools.get_tools_definition()

            try:
                # 1. Cancel previous tasks if they exist
                for task in [self.sender_task, self.receiver_task]:
                    if task and not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

                # 2. Reset state
                self.waiting_for_activity = False
                self.model_active = False
                self._speaking = False

                # Drain queue to avoid stale audio from previous sessions
                while not self.to_gemini_queue.empty():
                    try: self.to_gemini_queue.get_nowait()
                    except asyncio.QueueEmpty: break
                
                # 3. Configure and Connect
                # We use local context-injection memory for stability
                system_instruction_text = self.get_system_prompt()
                
                # INJECT MEMORY: Append history to system prompt
                if hasattr(self, 'conversation_memory') and self.conversation_memory:
                    history_text = "\n\n### CONVERSATION HISTORY (Previous Turns)\n"
                    for turn in self.conversation_memory:
                        history_text += f"- User: {turn['user']}\n- You: {turn['model']}\n"
                    system_instruction_text += history_text
                    self.log(f"Injected {len(self.conversation_memory)} turns of history into system prompt.")

                config = types.LiveConnectConfig(
                    response_modalities=[modality],
                    system_instruction=types.Content(parts=[types.Part(text=system_instruction_text)]),
                    # BARE BONES MODE: No Tools
                    # tools=tools_def, 
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
                        )
                    ),
                    # BARE BONES MODE: Manual VAD only (relies on Mumble sending audio)
                    # realtime_input_config=types.RealtimeInputConfig(
                    #     automatic_activity_detection=types.AutomaticActivityDetectionConfig(
                    #         start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    #         end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    #         silence_duration_ms=200, 
                    #     )
                    # ),
                    # DISABLE THINKING MODE
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                )

                self.gemini_session_ctx = self.client.aio.live.connect(model=MODEL_ID, config=config)
                self.gemini_session = await self.gemini_session_ctx.__aenter__()
                
                # UI FEEDBACK: Unmute self when connected
                if self.mumble and self.mumble.users.myself:
                    try: self.mumble.users.myself.unmute()
                    except: pass

                self.log(f"Gemini Session Ready (VERSION 2.1). (ID: {id(self.gemini_session)})")
                
                with contextlib.suppress(Exception):
                    chan = self.mumble.channels.get(self.mumble.users.myself['channel_id'])
                    chan.send_text_message("<b>Gemini Connected!</b>")
                
                # 4. Flush buffer (audio received while connecting)
                if hasattr(self, 'audio_buffer') and self.audio_buffer:
                    buf_count = len(self.audio_buffer)
                    self.log(f"Flushing {buf_count} buffered audio packets...")
                # 5. Start tasks
                self.sender_task = asyncio.create_task(self.sender_loop())
                self.receiver_task = asyncio.create_task(self.receiver_loop())
                
            except Exception as e:
                self.log(f"Gemini Connect Failed: {e}")
                await asyncio.sleep(5)
            
    async def disconnect_live_api(self):
        if self.gemini_session_ctx:
            with contextlib.suppress(Exception):
                await self.gemini_session_ctx.__aexit__(None, None, None)
        self.gemini_session = None

    async def sender_loop(self):
        self.log(f"sender_loop started (Session ID: {id(self.gemini_session)})")
        try:
            while self.is_running:
                # 0. Wait for session if not ready
                if not self.gemini_session or isinstance(self.gemini_session, str):
                    await asyncio.sleep(0.1)
                    continue

                try:
                    # 1. Wait for items with 0.5s timeout (Heartbeat)
                    item = await asyncio.wait_for(self.to_gemini_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    # 2. Heartbeat check
                    if not self.gemini_session or isinstance(self.gemini_session, str):
                        continue
                    
                    # Suppress heartbeats during model turns to avoid VAD confusion
                    if getattr(self, '_speaking', False) or getattr(self, 'model_active', False):
                        continue

                    # 100ms of silence (16kHz, 16bit mono = 3200 bytes)
                    item = b'\x00' * 3200
                
                if isinstance(item, bytes):
                    try:
                        self.sent_counter += 1
                        await self.gemini_session.send(input=types.LiveClientRealtimeInput(
                            media_chunks=[types.Blob(data=item, mime_type="audio/pcm;rate=16000")]
                        ))
                    except Exception as e:
                        self.log(f"ERROR: send_realtime_input Failed: {e}")
                        await self.disconnect_live_api()
                elif isinstance(item, str):
                    try:
                        self.log(f"DEBUG: sender_loop sending text: {item}")
                        await self.gemini_session.send(input=types.LiveClientContent(
                            turns=[types.Content(parts=[types.Part(text=item)], role="user")],
                            turn_complete=False
                        ))
                    except Exception as e:
                        self.log(f"ERROR: send_client_content Failed: {e}")
                        await self.disconnect_live_api()
        except asyncio.CancelledError: pass
        except Exception as e:
            self.log(f"!!! SENDER ERROR: {e} !!!")
            await self.disconnect_live_api()
            self.handle_disconnect()

    async def receiver_loop(self):
        self.log("receiver_loop started")
        self.model_active = False
        try:
            current_turn_input = []
            current_turn_output = []

            async for msg in self.gemini_session.receive():
                if msg.server_content:
                    self.model_active = True
                    # VAD: Check for Interruption
                    if msg.server_content.interrupted:
                        self.log(">>> Gemini Interrupted by User (Server Confirmed) <<<")
                        self.model_active = False
                        self._speaking = False
                        # We could clear mumble output buffer here if we had access
                        continue

                if msg.tool_call:
                    self.model_active = True
                
                # Usage Tracking
                if msg.usage_metadata:
                    self.total_tokens = msg.usage_metadata.total_token_count
                    self.update_comment()
                
                # Input Transcription (Logs & Memory)
                if msg.server_content and hasattr(msg.server_content, 'input_transcription') and msg.server_content.input_transcription:
                    text = msg.server_content.input_transcription.text
                    if text:
                        self.log_transcript("INPUT", text)
                        current_turn_input.append(text)

                # Output Transcription (Logs & Memory)
                if msg.server_content and hasattr(msg.server_content, 'output_transcription') and msg.server_content.output_transcription:
                    text = msg.server_content.output_transcription.text
                    if text:
                        self.log_transcript("OUTPUT", text)
                        current_turn_output.append(text)
                
                # Model Turn
                if msg.server_content and msg.server_content.model_turn:
                    parts = msg.server_content.model_turn.parts
                    for part in parts:
                        if part.text:
                            self.log(f"[TRANSCRIPT MODEL REAL] {part.text}")
                            # Text-only modes not handled here in this specific version
                        if part.inline_data:
                            if not (self.mumble.users.myself.get('mute') or self.mumble.users.myself.get('self_mute')):
                                pcm_len = len(part.inline_data.data)
                                if pcm_len > 0:
                                    if not getattr(self, '_speaking', False):
                                        self._speaking = True
                                        self.log(">>> SPEAKING START <<<")
                                    pcm = audioop.ratecv(part.inline_data.data, 2, 1, 24000, 48000, None)[0]
                                    self.mumble.sound_output.add_sound(pcm)

                # Tool Call
                if msg.tool_call:
                    for call in msg.tool_call.function_calls:
                        await self.handle_tool_call(call)
                
                if msg.server_content and msg.server_content.turn_complete:
                    self.total_requests += 1
                    self.update_comment()
                    
                    if getattr(self, '_speaking', False):
                        self._speaking = False
                        self.log(">>> SPEAKING END <<<")
                    
                    self.log("Turn Complete")
                    
                    # Store to conversation memory
                    user_text = " ".join(current_turn_input).strip()
                    model_text = " ".join(current_turn_output).strip()
                    if user_text or model_text:
                        if not hasattr(self, 'conversation_memory'): self.conversation_memory = []
                        self.conversation_memory.append({"user": user_text, "model": model_text})
                        self.log(f"DEBUG: Memory updated. History size: {len(self.conversation_memory)}")
                    
                    # Reset current turn buffers
                    current_turn_input = []
                    current_turn_output = []

                    # Session Reset Strategy: Disconnect to force VAD reset for next turn.
                    # This adds latency (~3s) but guarantees the model will listen to Turn 2.
                    # Persistent sessions cause "Turn 2 Silence" bug with this model/API version.
                    self.log("Turn Complete. Resetting session for stability...")
                    await self.disconnect_live_api()
                    self._speaking = False
                    return # Exit receiver loop (sender loop will restart when session disconnects)
                    
                    # BARE BONES MODE: Persistent Session (Disable Session Reset)
                    # self._speaking = False

        except asyncio.CancelledError: pass
        except Exception as e:
            self.log(f"!!! RECEIVER ERROR ({type(e).__name__}): {e} !!!")
            await self.disconnect_live_api()
            self.handle_disconnect()

    async def handle_tool_call(self, call):
        result = await tools.dispatch_tool_call(self, call)
        # Send tool response
        if self.gemini_session:
            self.log(f"DEBUG: Sending tool response for {call.name} (Result: {result[:50]}...)")
            await self.gemini_session.send(input=types.LiveClientToolResponse(
                function_responses=[types.FunctionResponse(
                    name=call.name, id=call.id, response={"result": result}
                )]
            ))
            # Proactively send a heartbeat after tool response to signal "keep listening"
            self.to_gemini_queue.put_nowait(b'\x00' * 6440) 

    def handle_disconnect(self):
        """Called when the Gemini session ends. Sets waiting_for_activity to pause reconnection until audio resumes."""
        self.dropout_counts += 1
        self.last_disconnect_time = time.time()
        self.waiting_for_activity = True
        
        # UI FEEDBACK: Mute self when disconnected
        if self.mumble and self.mumble.users.myself:
            try: self.mumble.users.myself.mute()
            except: pass
            
        self.log("Session ended. Muted Mumble. Waiting for audio activity before reconnecting...")

    def sound_received(self, user, sound):
        """
        Core audio reception callback. Resamples Mumble audio (48kHz) to Gemini format (16kHz),
        handles activity detection, interruption, and pushes audio to the Gemini queue.
        """
        self.sound_counter += 1
        
        try:
            pcm_data = sound.pcm
            # Resample from 48000 to 16000 for Gemini
            resampled = audioop.ratecv(pcm_data, 2, 1, 48000, 16000, None)[0]
            rms = audioop.rms(resampled, 2)
            
            # 1. Wake up if waiting for activity
            if self.waiting_for_activity:
                # Buffer the audio so we don't lose the start of the sentence
                self.audio_buffer.append(resampled)

                if self.sound_counter % 50 == 0:
                     self.log(f"Waiting for activity... RMS: {rms}")
                
                # Sensitivity threshold
                if rms > 150: 
                    self.log(f"Audio activity detected (RMS: {rms}) - flagging for reconnection")
                    self.waiting_for_activity = False
                else:
                    return # Still waiting
            
            # 2. Interruption Handling
            if getattr(self, '_speaking', False) and rms > 1000:
                self.log(f"Interruption detected (RMS: {rms}) - Clearing local audio buffer")
                self.mumble.sound_output.clear_buffer()
            
            # 3. Session-loss Buffering
            if not self.gemini_session or isinstance(self.gemini_session, str):
                if not hasattr(self, 'audio_buffer'):
                    self.audio_buffer = collections.deque(maxlen=100)
                self.audio_buffer.append(resampled)
                if len(self.audio_buffer) % 50 == 0:
                    self.log(f"DEBUG: sound_received buffering ({len(self.audio_buffer)} packets, RMS: {rms})")
                return
            
            self.received_counter += 1
            if self.received_counter % 100 == 0:
                self.log(f"DEBUG: sound_received putting to queue (Packets: {self.received_counter})")
            
            name = user.get('name')
            if name != self.current_speaker:
                self.current_speaker = name
            
            # Send everything to Gemini
            try:
                self.to_gemini_queue.put_nowait(resampled)
            except Exception as qe:
                self.log(f"DEBUG: Queue put failed: {qe}")

        except Exception as e:
            self.log(f"DEBUG: sound_received error: {e}")
