import asyncio
import os
import time
import subprocess
import pymumble_py3 as pymumble
from pymumble_py3.errors import UnknownChannelError

# --- CONFIG ---
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_UNDER_TEST = os.getenv("BENNY_NAME", "Benny Botman")
DRIVER_NAME = "Live Voice Test"
TEST_ROOM = "AI Test Room"
CERT = "/bots/certs/tester.pem"
KEY = "/bots/certs/tester_key.pem"

class MultiTurnDriver:
    def __init__(self):
        self.mumble = None
        self.benny_user = None

    async def connect(self):
        print(f"[System] Connecting {DRIVER_NAME} to {MUMBLE_HOST} using {CERT}...")
        self.mumble = pymumble.Mumble(MUMBLE_HOST, DRIVER_NAME, port=64738, certfile=CERT, keyfile=KEY)
        self.mumble.set_receive_sound(True)
        self.mumble.start()
        
        # Wait until fully connected and synced
        # NOTE: is_ready() BLOCKS until server sync completes and returns None.
        # Never use it as a boolean (`while not is_ready()` spins forever).
        await asyncio.to_thread(self.mumble.is_ready)
            
        self.mumble.users.myself.unmute()
        self.mumble.users.myself.undeafen()
        print(f"[System] {DRIVER_NAME} connected.")


    async def ensure_test_room(self):
        print(f"[System] Ensuring {TEST_ROOM} exists...")
        
        # 1. Find Hallway
        hallway = next((c for c in self.mumble.channels.values() if "Hallway" in c.get("name", "")), None)
        if not hallway:
            print("[Error] Hallway channel not found!")
            return None
        
        # 2. Check/Create Test Room
        ai_test_id = None
        try:
            ai_test = self.mumble.channels.find_by_name(TEST_ROOM)
            ai_test_id = ai_test['channel_id']
            print(f"[System] Found existing {TEST_ROOM} (ID: {ai_test_id}).")
        except UnknownChannelError:
            print(f"[System] Creating {TEST_ROOM} under Hallway (ID: {hallway['channel_id']})...")
            # Create as temporary so it cleans up if the test crashes
            self.mumble.channels.new_channel(hallway['channel_id'], TEST_ROOM, temporary=True)
            # Give Murmur some time to propagate the new channel and refresh state
            await asyncio.sleep(5)

            # Debug: dump known channels for diagnosis
            try:
                ch_list = [(c.get('channel_id'), c.get('name')) for c in self.mumble.channels.values()]
                print(f"[Debug] Channels after creation attempt: {ch_list}")
            except Exception as e:
                print(f"[Debug] Could not enumerate channels: {e}")

            # Try a few times to locate the created channel before giving up
            found = False
            for attempt in range(5):
                try:
                    ai_test = self.mumble.channels.find_by_name(TEST_ROOM)
                    if ai_test:
                        ai_test_id = ai_test['channel_id']
                        print(f"[System] Successfully created {TEST_ROOM} (ID: {ai_test_id}).")
                        found = True
                        break
                except UnknownChannelError:
                    pass
                await asyncio.sleep(1)

            # If not found after retries, fallback to a suitable existing channel
            if not found:
                print(f"[Error] Failed to find {TEST_ROOM} after creation! Falling back to an existing suitable channel.")
                # Fallback: prefer Mic Check, then Stage, then Backstage, then Audience
                preferred_order = ["Mic Check", "Stage", "Backstage", "Audience"]
                channels_by_name = { (c.get('name') or ''): c for c in self.mumble.channels.values() }
                fallback_candidates = []
                for pref in preferred_order:
                    for c in self.mumble.channels.values():
                        name = c.get('name') or ''
                        if pref in name:
                            fallback_candidates.append(c)
                # If none matched in preferred order, fallback to any of the other candidates
                if not fallback_candidates:
                    fallback_candidates = [
                        c for c in self.mumble.channels.values()
                        if any(k in (c.get('name') or '') for k in ("Stage", "Audience", "Mic Check", "Backstage"))
                    ]
                if fallback_candidates:
                    chosen = fallback_candidates[0]
                    ai_test_id = chosen.get('channel_id')
                    print(f"[Fallback] Using existing channel '{chosen.get('name')}' (ID: {ai_test_id}) for tests.")
                else:
                    # As a last resort, use the Hallway itself
                    ai_test_id = hallway['channel_id']
                    print(f"[Fallback] No suitable child channel found; using Hallway (ID: {ai_test_id}).")


        # 3. Move self to the room
        self.mumble.users.myself.move_in(ai_test_id)
        return ai_test_id

    async def wait_for_benny(self, target_channel_id):
        print(f"[System] Waiting for {BOT_UNDER_TEST} to join {TEST_ROOM}...")
        for i in range(45):
            # 1. Find the LATEST bot session (highest ID) to avoid zombies
            candidates = [u for u in self.mumble.users.values() if u['name'] == BOT_UNDER_TEST]
            if candidates:
                benny = max(candidates, key=lambda x: x['session'])
                
                # 2. Check channel
                if benny['channel_id'] == target_channel_id:
                    print(f"[System] {BOT_UNDER_TEST} (Session {benny['session']}) is in channel {benny['channel_id']}. Waiting for UNDEAFEN...")
                    
                    # 3. Wait for undeafen (max 25s)
                    for wait_tick in range(50):
                        u_state = self.mumble.users.get(benny['session'])
                        if u_state:
                            # SPEC-ALIGNED: Standby mode is Undeafened
                            is_deafened = u_state.get('self_deafen', False)
                            
                            if not is_deafened:
                                print(f"[System] {BOT_UNDER_TEST} (Session {benny['session']}) is undeafened and listening.")
                                self.benny_user = u_state
                                return True
                        
                        if wait_tick % 10 == 0:
                            print(f"  [Wait] Syncing state... Session: {benny['session']} (Tick {wait_tick})")
                        await asyncio.sleep(0.5)
                    
                    print(f"[FAIL] {BOT_UNDER_TEST} joined but timed out waiting for UNDEAFEN.")
                    return "UNDEAFEN_TIMEOUT"
                else:
                    if i % 5 == 0:
                        print(f"[System] {BOT_UNDER_TEST} (Session {benny['session']}) found but in channel {benny['channel_id']}, expected {target_channel_id}")

            
            if i % 10 == 0:
                print(f"[System] Still waiting for {BOT_UNDER_TEST}... (Users: {[u['name'] for u in self.mumble.users.values()]})")
            await asyncio.sleep(1)
        return "JOIN_TIMEOUT"

    async def play_clip(self, filename):
        """Play an audio clip through ffmpeg in a non-blocking async manner.
        This avoids blocking the tester's event loop while streaming to Mumble.
        """
        path = f"/bots/clips/{filename}"
        print(f"[Driver] Playing {filename}...")
        # Diagnostics: ensure file exists and report size
        try:
            stat = os.stat(path)
            print(f"[Driver] Clip exists: {path} size={stat.st_size} bytes")
        except FileNotFoundError:
            print(f"[Driver] ERROR: Clip not found: {path}")
            return
        cmd = ["ffmpeg", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "48000", "-"]

        # Capture stderr so we can print ffmpeg errors for diagnostics
        print(f"[Driver] Starting ffmpeg with cmd: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except Exception as e:
            print(f"[Driver] Failed to start ffmpeg: {e}")
            return
        try:
            bytes_sent = 0
            # Send in 20ms frames (1920 bytes at 48kHz 16-bit mono) to match Mumble frame expectations.
            # CRITICAL: must feed add_sound at REAL-TIME rate (1920B per 20ms).
            # Underfeeding (e.g. 640B/20ms) starves pymumble's encoder loop, which
            # pads the gap with garbage — the bot then receives VAD-poisoned audio.
            frame_size = 1920
            frame_sleep = 0.02
            while True:
                data = await proc.stdout.read(frame_size)
                if not data:
                    break
                bytes_sent += len(data)
                # Diagnostic: persist first few frames to inspect what we're sending
                try:
                    if not hasattr(self, '_diag_written'):
                        self._diag_written = 0
                    if self._diag_written < 4:
                        with open(f"/tmp/tester_sent_{self._diag_written}.pcm", "ab") as f:
                            f.write(data)
                        self._diag_written += 1
                except Exception:
                    pass
                try:
                    # Push PCM frames into the Mumble sound output
                    self.mumble.sound_output.add_sound(data)
                except Exception as e:
                    print(f"[Driver] Warning: add_sound raised: {e}")
                # Sleep for the frame duration to avoid flooding the server
                await asyncio.sleep(frame_sleep)
        finally:
            returncode = await proc.wait()
            if returncode != 0:
                stderr = (await proc.stderr.read()).decode(errors='replace') if proc.stderr is not None else ''
                print(f"[Driver] ffmpeg exited with code {returncode}. Stderr:\n{stderr}")
            else:
                # Drain stderr silently to avoid broken pipe
                if proc.stderr is not None:
                    await proc.stderr.read()
            print(f"[Driver] Streamed {bytes_sent} bytes for {filename}")

    async def run_test(self):
        await self.connect()
        
        tid = await self.ensure_test_room()
        if tid is None: return False
        
        status = await self.wait_for_benny(tid)
        if status == "JOIN_TIMEOUT":
            print(f"[FAIL] {BOT_UNDER_TEST} timed out waiting to join {TEST_ROOM}.")
            return False
        if status == "UNMUTE_TIMEOUT":
            print(f"[FAIL] {BOT_UNDER_TEST} joined {TEST_ROOM} but remained MUTED.")
            return False

        clips = [
            "hey-benny-can-you-hear-me.opus",
            "hey-benny-name-all-the-channels.opus",
            "create-a-channel-then-move-to-it.opus"
        ]

        for i, clip in enumerate(clips):
            print(f"\n--- TURN {i+1}: {clip} ---")
            # play_clip is async now; call and allow background tasks to proceed
            await self.play_clip(clip)

            print(f"[System] Monitoring {BOT_UNDER_TEST} for response...")
            start_wait = time.time()
            responded = False
            
            while time.time() - start_wait < 15:
                sid = self.benny_user['session']
                u = self.mumble.users.get(sid)
                
                # Check sound state robustly
                is_sc = u.sound.is_sound() if u else False
                is_sp = u.get('is_speaking', False) if u else False
                
                if time.time() - start_wait > 5 and int(time.time() - start_wait) % 5 == 0:
                    print(f"  [Waiting for Response] User={u['name'] if u else 'N/A'}, Session={sid}, Speaking={is_sp}, Sound={is_sc}")

                if u and (is_sp or is_sc):
                    print(f"[System] {BOT_UNDER_TEST} started speaking (Sound={is_sc}, Speak={is_sp})")
                    # Wait for silence
                    silence_start = None
                    last_debug = time.time()
                    while True:
                        await asyncio.sleep(0.02) # Faster polling for draining
                        u = self.mumble.users.get(sid)
                        
                        # IMPORTANT: We MUST drain the sound buffer or is_sound stays True
                        if u and u.sound.is_sound():
                            u.sound.get_sound() # Drain and discard
                        
                        sc = u.sound.is_sound() if u else False
                        sp = u.get('is_speaking', False) if u else False
                        
                        if time.time() - last_debug > 2.0:
                             print(f"  [Silence Loop] Sound={sc}, Speak={sp}, SilenceTime={0 if silence_start is None else time.time() - silence_start:.1f}s")
                             last_debug = time.time()

                        if not u or not (sc or sp):
                             if silence_start is None:
                                 silence_start = time.time()
                             elif time.time() - silence_start > 1.2: # 1.2s of solid silence
                                 break
                        else:
                             silence_start = None
                    
                    print(f"[System] {BOT_UNDER_TEST} finished speaking.")
                    responded = True
                    break
                await asyncio.sleep(0.1)

            if not responded:
                print(f"[FAIL] {BOT_UNDER_TEST} failed to respond.")
                return False
            
            await asyncio.sleep(1.0)

        print("\n\u2705 MULTI-TURN TEST PASSED")
        return True

if __name__ == "__main__":
    driver = MultiTurnDriver()
    try:
        if not asyncio.run(driver.run_test()):
            exit(1)
    finally:
        if driver.mumble:
            driver.mumble.stop()
