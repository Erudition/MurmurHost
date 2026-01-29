import asyncio
import os
import time
import audioop
import subprocess
import pymumble_py3 as pymumble
from google import genai
from google.genai import types

# --- CONFIG ---
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_ID = "models/gemini-2.5-flash-native-audio-preview-12-2025"
MUMBLE_HOST = "murmur"

class MultiTurnTester:
    def __init__(self):
        self.transcripts = []
        self.benny_ready = asyncio.Event()
        self.current_turn_done = asyncio.Event()

    async def run_benny(self):
        print(f"[Benny] Starting client with token len: {len(API_KEY) if API_KEY else 'NONE'}...")
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1alpha'})
        
        config = {"generation_config": {
            "response_modalities": ["AUDIO"],
            "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": "Fenrir"}}}
        }}

        try:
            print("[Benny] Initiating Gemini connect...")
            async with client.aio.live.connect(model=MODEL_ID, config=config) as session:
                print("[Benny] Gemini session connected successfully.")
                self.session = session
                
                # Start receiver
                receiver_task = asyncio.create_task(self.receiver_loop())
                self.benny_ready.set()
                
                # Simple sender loop for bytes
                self.queue = asyncio.Queue()
                while True:
                    try:
                        item = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                        await self.session.send_realtime_input(media=types.Blob(data=item, mime_type="audio/pcm;rate=16000"))
                    except asyncio.TimeoutError:
                        # Keep-alive
                        await self.session.send_realtime_input(media=types.Blob(data=b'\x00'*3200, mime_type="audio/pcm;rate=16000"))
        except Exception as e:
            print(f"[Benny] Gemini error: {e}")
        finally:
            print("[Benny] Client/session closed.")

    async def receiver_loop(self):
        async for msg in self.session.receive():
            if msg.server_content and msg.server_content.model_turn:
                for part in msg.server_content.model_turn.parts:
                    if part.text:
                        print(f"[Gemini Response] {part.text}")
                        self.transcripts.append(part.text)
            if msg.server_content and msg.server_content.turn_complete:
                print("[Benny] Turn complete.")
                self.current_turn_done.set()

    def sound_received(self, user, sound):
        if user['name'] == "TestDriver":
            pcm = sound.pcm
            resampled = audioop.ratecv(pcm, 2, 1, 48000, 16000, None)[0]
            self.queue.put_nowait(resampled)

    async def check_certs(self):
        for base, p in [("test", "/tmp/test_cert.pem"), ("test2", "/tmp/test_cert_2.pem")]:
            key_p = p.replace(".pem", "_key.pem")
            if not os.path.exists(p) or not os.path.exists(key_p):
                print(f"[System] Generating {p} and {key_p}...")
                subprocess.run([
                    "openssl", "req", "-x509", "-newkey", "rsa:2048", 
                    "-keyout", key_p, "-out", p, 
                    "-days", "1", "-nodes", "-subj", f"/CN={base}"
                ], check=True, capture_output=True)
            else:
                print(f"[System] Certs exist: {p}, {key_p}")

    async def run_test(self):
        await self.check_certs()
        print("[System] Connecting Benny to Mumble...")
        m_benny = pymumble.Mumble(MUMBLE_HOST, "BennyBot", port=64738, 
                                  certfile="/tmp/test_cert.pem", keyfile="/tmp/test_cert_key.pem")
        m_benny.start()
        m_benny.is_ready()
        m_benny.users.myself.deaf = False
        m_benny.users.myself.mute = False
        m_benny.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        
        print("[System] Connecting TestDriver to Mumble...")
        m_driver = pymumble.Mumble(MUMBLE_HOST, "TestDriver", port=64738,
                                   certfile="/tmp/test_cert_2.pem", keyfile="/tmp/test_cert_2_key.pem")
        m_driver.start()
        m_driver.is_ready()
        m_driver.users.myself.mute = False

        # Join room
        target_chan = list(m_benny.channels.values())[0]['channel_id']
        for c in m_benny.channels.values():
            if c['name'] == 'AI Test Room': target_chan = c['channel_id']; break
        
        m_benny.users.myself.move_in(target_chan)
        m_driver.users.myself.move_in(target_chan)
        
        # Start Gemini
        benny_task = asyncio.create_task(self.run_benny())
        await self.benny_ready.wait()

        def play_sync(file):
            print(f"[Driver] Playing {file}...")
            proc = subprocess.Popen(["ffmpeg", "-i", "/bots/test-speech-clips/" + file, "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            while True:
                data = proc.stdout.read(1920)
                if not data: break
                m_driver.sound_output.add_sound(data)
                time.sleep(0.015)
            proc.wait()

        clips = ["hey-benny-can-you-hear-me.opus", "hey-benny-can-you-move-rooms.opus", "check-check-123.opus"]
        for i, clip in enumerate(clips):
            print(f"-- TURN {i+1} --")
            self.current_turn_done.clear()
            play_sync(clip)
            print("[System] Waiting for response...")
            try:
                await asyncio.wait_for(self.current_turn_done.wait(), timeout=30)
            except:
                print("[System] Turn timeout, moving to next.")
            time.sleep(2)

        print("\n=== FINAL TRANSCRIPTS ===")
        for t in self.transcripts:
            print(f"- {t}")
        
        m_benny.stop()
        m_driver.stop()
        benny_task.cancel()

if __name__ == "__main__":
    tester = MultiTurnTester()
    asyncio.run(tester.run_test())
