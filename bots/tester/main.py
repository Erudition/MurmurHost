import asyncio
import os
import time
import subprocess
import pymumble_py3 as pymumble
from pymumble_py3.errors import UnknownChannelError

# --- CONFIG ---
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_UNDER_TEST = "Benny Botman"
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
        await asyncio.to_thread(self.mumble.is_ready)
        self.mumble.users.myself.unmute()
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
            await asyncio.sleep(2)
            try:
                ai_test = self.mumble.channels.find_by_name(TEST_ROOM)
                ai_test_id = ai_test['channel_id']
                print(f"[System] Successfully created {TEST_ROOM} (ID: {ai_test_id}).")
            except UnknownChannelError:
                print(f"[Error] Failed to find {TEST_ROOM} after creation!")
                return None

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
                    print(f"[System] {BOT_UNDER_TEST} (Session {benny['session']}) is in channel {benny['channel_id']}. Waiting for UNMUTE...")
                    
                    # 3. Wait for unmute (max 25s)
                    for wait_tick in range(50):
                        u_state = self.mumble.users.get(benny['session'])
                        if u_state:
                            # If self_mute is missing, it means the user is in default (unmuted) state
                            is_muted = u_state.get('self_mute', False)
                            
                            if not is_muted:
                                print(f"[System] {BOT_UNDER_TEST} (Session {benny['session']}) is listening.")
                                self.benny_user = u_state
                                return True
                        
                        if wait_tick % 10 == 0:
                            print(f"  [Wait] Syncing state... Session: {benny['session']} (Tick {wait_tick})")
                        await asyncio.sleep(0.5)
                    
                    print(f"[FAIL] {BOT_UNDER_TEST} joined but timed out waiting for UNMUTE.")
                    return "UNMUTE_TIMEOUT"
            
            if i % 10 == 0:
                print(f"[System] Still waiting for {BOT_UNDER_TEST}... (Users: {[u['name'] for u in self.mumble.users.values()]})")
            await asyncio.sleep(1)
        return "JOIN_TIMEOUT"

    def play_clip(self, filename):
        path = f"/bots/clips/{filename}"
        print(f"[Driver] Playing {filename}...")
        cmd = ["ffmpeg", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "48000", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        while True:
            data = proc.stdout.read(1920)
            if not data: break
            self.mumble.sound_output.add_sound(data)
            time.sleep(0.015)
        proc.wait()

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
            self.play_clip(clip)

            print(f"[System] Monitoring {BOT_UNDER_TEST} for response...")
            start_wait = time.time()
            responded = False
            
            while time.time() - start_wait < 5:
                sid = self.benny_user['session']
                u = self.mumble.users.get(sid)
                
                # Check sound state robustly
                is_sc = u.sound.is_sound() if u else False
                is_sp = u.get('is_speaking', False) if u else False
                
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
