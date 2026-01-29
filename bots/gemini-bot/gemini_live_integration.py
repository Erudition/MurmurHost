import asyncio
import os
import time
import audioop
import collections
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

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
                "system_instruction": self.get_system_prompt(),
                "tools": tools,
            }
            
            # Always include AUDIO config for stability
            config.update({
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": VOICE_NAME}}
                },
                "output_audio_transcription": {},
                "input_audio_transcription": {},
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
        if hasattr(self, 'sender_task') and self.sender_task: self.sender_task.cancel()
        if hasattr(self, 'receiver_task') and self.receiver_task: self.receiver_task.cancel()

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
                chan.send_text_message(f"<b>{self.bot_name}:</b> {args['message']}")
            elif name == "send_direct_message":
                target_user = None
                for u in self.mumble.users.values():
                    if u['name'] == args['username']:
                        target_user = u
                        break
                if target_user:
                    target_user.send_text_message(f"<b>(Private) {self.bot_name}:</b> {args['message']}")
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
