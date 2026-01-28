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
VOICE_NAME = "Charon"
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_NAME = os.getenv("MUMBLE_USER", "PodBot")
API_KEY = os.getenv("GEMINI_API_KEY")

AUDIENCE_CHANNEL = "Audience 👂"
STAGE_CHANNEL = "🎙️ Stage 🔴"

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
        self.total_requests = 0
        self.current_modality = "AUDIO"
        
    def log(self, text):
        print(f"[{BOT_NAME}] {text}", flush=True)

    async def connect_mumble(self):
        self.log(f"Connecting to Mumble at {MUMBLE_HOST} as {BOT_NAME}...")
        self.mumble = pymumble.Mumble(MUMBLE_HOST, BOT_NAME, port=64738)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        self.mumble.start()
        
        for _ in range(20):
            if self.mumble.is_ready() and self.mumble.users.myself: break
            await asyncio.sleep(0.5)
            
        if not self.mumble.users.myself:
            raise Exception("Mumble Connection Failed")
            
        self.mumble.set_receive_sound(True)
        self.update_comment()

    def update_comment(self):
        # "Tokens: 45k/1M | Reqs: 125/250"
        msg = (f"<b>PodBot (Gemini 2.5)</b><br/>"
               f"Usage: {self.total_tokens} tokens<br/>"
               f"Requests: {self.total_requests}")
        try:
             self.mumble.users.myself.comment(msg)
        except: pass

    async def connect_live_api(self, modality):
        self.log(f"Connecting to Gemini Live API (Modality: {modality})...")
        config = {
             "response_modalities": [modality],
             "speech_config": {
                 "voice_config": {"prebuilt_voice_config": {"voice_name": VOICE_NAME}}
             },
             "enable_affective_dialog": True,
             "proactive_audio": True,
             "output_audio_transcription": True,
             "input_audio_transcription": True,
        }
        
        try:
            self.gemini_session_ctx = self.client.aio.live.connect(model=MODEL_ID, config=config)
            self.gemini_session = await self.gemini_session_ctx.__aenter__()
            self.current_modality = modality
            self.log("Gemini Session Ready.")
            
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
        try:
            while True:
                item = await self.to_gemini_queue.get()
                if self.gemini_session:
                    if isinstance(item, bytes):
                        await self.gemini_session.send(input=types.LiveClientRealtimeInput(
                            media_chunks=[types.LiveClientMediaChunk(data=item, mime_type="audio/pcm;rate=16000")]
                        ))
                    elif isinstance(item, str):
                        await self.gemini_session.send(input=types.LiveClientContent(
                            parts=[types.Part(text=item)]
                        ), end_of_turn=False)
        except asyncio.CancelledError: pass
        except Exception as e:
            self.log(f"Sender Error: {e}")

    async def receiver_loop(self):
        try:
            async for msg in self.gemini_session.receive():
                # Usage Tracking
                if msg.usage_metadata:
                    self.total_tokens = msg.usage_metadata.total_token_count
                    self.update_comment()
                
                # Input Transcription (Logs)
                if msg.server_content and msg.server_content.input_audio_transcription:
                    print(f"[TRANSCRIPT INPUT] {msg.server_content.input_audio_transcription.text}")

                # Model Turn
                if msg.server_content and msg.server_content.model_turn:
                    # Model Transcription (Logs)
                    if msg.server_content.model_turn.parts:
                        for part in msg.server_content.model_turn.parts:
                            if part.text:
                                print(f"[TRANSCRIPT MODEL] {part.text}")
                                if self.current_modality == "TEXT":
                                    # Send to channel
                                    chan = self.mumble.channels.get(self.mumble.users.myself['channel_id'])
                                    chan.send_text_message(f"<b>Gemini:</b> {part.text}")
                            if part.inline_data:
                                pcm = audioop.ratecv(part.inline_data.data, 2, 1, 24000, 48000, None)[0]
                                self.mumble.sound_output.add_sound(pcm)
                
                if msg.server_content and msg.server_content.turn_complete:
                     # Check if model chose NOT to respond (Proactive Audio logic)
                     # In Gemini Live, if turn_complete is received without any model_turn parts, 
                     # it means it didn't find anything relevant to say.
                     # However, proactivity might also trigger 'silent' turns.
                     # Requirement: "move itself back to Audience in this case"
                     self.total_requests += 1
                     self.update_comment()
                     
                     # Check for silence/no-response
                     # (This heuristic might need tuning)
                     # For now, let's assume if we are on Stage and the model is quiet, we might move.
                     pass

        except asyncio.CancelledError: pass
        except Exception as e:
            self.log(f"Receiver Error: {e}")

    def sound_received(self, user, sound):
        if not self.gemini_session: return
        try:
            resampled = audioop.ratecv(sound.pcm, 2, 1, 48000, 16000, None)[0]
            name = user.get('name')
            if name != self.current_speaker:
                self.current_speaker = name
                self.to_gemini_queue.put_nowait(f"[Speaker: {name}]")
            self.to_gemini_queue.put_nowait(resampled)
        except: pass

    async def run(self):
        await self.connect_mumble()
        
        while self.is_running:
            try:
                user = self.mumble.users.myself
                my_chan = self.mumble.channels.get(user['channel_id'])
                
                # Permission check proxy
                on_stage = (my_chan and my_chan['name'] == STAGE_CHANNEL)
                is_deafened = user.get('self_deaf', False) or user.get('deaf', False)
                is_muted = user.get('self_mute', False) or user.get('mute', False)
                
                # Rule: permissions to speak (currently just the Stage)
                if not on_stage:
                    if self.gemini_session:
                        await self.disconnect_live_api()
                else:
                    if is_deafened:
                        if self.gemini_session:
                            await self.disconnect_live_api()
                    else:
                        # Should be connected
                        modality = "TEXT" if is_muted else "AUDIO"
                        
                        if not self.gemini_session:
                            await self.connect_live_api(modality)
                        elif self.current_modality != modality:
                            await self.disconnect_live_api()
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
