import asyncio
import os
import sys
import time
import subprocess
import pymumble_py3 as pymumble
from pymumble_py3.constants import *

# Configuration
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_NAME = "Supervisor"
TARGET_STAGE = "🎙️ Stage 🔴"
MIC_CHECK_CHANNEL = "Mic Check 🎧"

class SupervisorBot:
    def __init__(self):
        self.mumble = None
        self.is_running = True
        
        # Bot Lifecycle Management
        # { name: { 'process': proc, 'kick_state_users': set(), 'should_be_online': bool, 'kick_wait': bool, 'last_start_attempt': timestamp } }
        self.bots = {
            "Echo": {"script": "/bots/echobot.py", "process": None, "should_be_online": False, "kick_wait": False, "kick_state_users": set(), "last_start_attempt": 0},
            "Recording": {"script": "/bots/opus_recorder.py", "process": None, "should_be_online": False, "kick_wait": False, "kick_state_users": set(), "last_start_attempt": 0},
            "PodBot": {"script": "/bots/gemini-bot/bot.py", "process": None, "should_be_online": False, "kick_wait": False, "kick_state_users": set(), "last_start_attempt": 0}
        }
        
        self.verified_users = {} # {username: timestamp_last_seen}
        self.user_mic_check_entry = {} # {username: entry_timestamp}
        
    def mumble_connected(self):
        print(f"Supervisor Connected to Mumble as {BOT_NAME}")
        
        # Enforce "Observer" State
        try:
            self.mumble.users.myself.deafen()
            self.mumble.users.myself.mute()
        except: pass
        
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)

    def sound_received(self, user, sound):
        """Used to detect audio activity for mic check verification"""
        name = user.get('name')
        if name and name in self.user_mic_check_entry:
            # If they are in Mic Check and speaking, they are verified
            if time.time() - self.user_mic_check_entry[name] > 3.0:
                if name not in self.verified_users:
                    print(f"Supervisor: User {name} verified via Audio + Time.")
                    user.send_text_message("✅ <b>Mic Check Complete</b>. You are verified.")
                self.verified_users[name] = time.time()

    def update_status_comment(self):
        """Updates the Supervisor's User Comment with the status of all bots and reasons."""
        report = "<b>Studio Supervisor Status</b><br/>"
        report += f"<i>Last Updated: {time.strftime('%H:%M:%S')}</i><br/><br/>"
        
        for name, data in self.bots.items():
            status = "🟢 Online" if data['process'] and data['process'].poll() is None else "🔴 Offline"
            reason = ""
            if status == "🔴 Offline":
                if name == "Echo":
                    reason = " (Waiting for humans/unverified users)"
                elif name in ["Recording", "PodBot"]:
                    if not data.get('should_be_online'):
                        reason = " (Stage empty or waiting for new users after kick)"
                    else:
                        reason = " (Starting...)"
            
            report += f"<b>{name}</b>: {status}{reason}<br/>"

        # Show verified users
        if self.verified_users:
            report += "<br/><b>Verified Humans:</b><br/>"
            now = time.time()
            for u, t in list(self.verified_users.items()):
                if now - t < 60:
                    report += f"- {u} ({int(60 - (now - t))}s remaining)<br/>"
                else:
                    del self.verified_users[u]

        try:
            self.mumble.users.myself.comment(report)
        except: pass

    def get_presence_info(self):
        """Analyzes the server and returns raw sets of humans in various locations."""
        humans = set()
        stage_humans = set()
        mic_check_humans = set()
        unverified_humans = False
        
        mc_chan = None
        st_chan = None
        try:
            mc_chan = self.mumble.channels.find_by_name(MIC_CHECK_CHANNEL)
            st_chan = self.mumble.channels.find_by_name(TARGET_STAGE)
        except: pass

        for user in self.mumble.users.values():
            name = user.get('name')
            if not name or name in [BOT_NAME, "Echo", "Recording", "PodBot"]:
                continue
            
            humans.add(name)
            chan_id = user.get('channel_id')
            
            if st_chan and chan_id == st_chan['channel_id']:
                stage_humans.add(name)
                
            if mc_chan and chan_id == mc_chan['channel_id']:
                mic_check_humans.add(name)
                if name not in self.user_mic_check_entry:
                    self.user_mic_check_entry[name] = time.time()
            else:
                if name in self.user_mic_check_entry:
                    del self.user_mic_check_entry[name]

            # Check verification persistence
            if name in self.verified_users:
                self.verified_users[name] = time.time() # Keep alive while present
            else:
                unverified_humans = True
        
        return humans, stage_humans, mic_check_humans, unverified_humans

    def get_presence_stats_from_info(self, humans, stage_humans, mic_check_humans, unverified_humans):
        """Calculates which bots should be on based on info sets."""
        # ECHO BOT LOGIC:
        echo_should_be_on = len(humans) > 0 and (len(mic_check_humans) > 0 or unverified_humans)
        
        # REC/PODBOT LOGIC:
        rec_should_be_on = self.check_kick_aware_presence("Recording", stage_humans)
        pod_should_be_on = self.check_kick_aware_presence("PodBot", stage_humans)
        
        return echo_should_be_on, rec_should_be_on, pod_should_be_on

    def check_kick_aware_presence(self, bot_name, current_stage_humans):
        data = self.bots[bot_name]
        
        # If process is running, we aren't in a "Kicked" state waiting for re-entry.
        if data['process'] and data['process'].poll() is None:
            # If it's running but stage becomes empty, it should stop.
            return len(current_stage_humans) > 0

        # If it's NOT running, check if it was previously kicked/stopped.
        # If stage is empty, definitely stay off.
        if len(current_stage_humans) == 0:
            data['kick_state_users'] = set()
            return False

        # If stage has people, check if we are waiting for NEW people.
        if not data.get('kick_wait', False):
            # Fresh join condition
            return True
        else:
            # We are in kick-wait. Check for positive change.
            new_people = current_stage_humans - data.get('kick_state_users', set())
            if new_people:
                print(f"Supervisor: {bot_name} kick-wait cleared by {new_people}")
                data['kick_wait'] = False
                return True
            return False

    def manage_processes(self, echo, rec, pod):
        # Update should_be_online for status reporting
        self.bots['Echo']['should_be_online'] = echo
        self.bots['Recording']['should_be_online'] = rec
        self.bots['PodBot']['should_be_online'] = pod
        
        for name, on in [("Echo", echo), ("Recording", rec), ("PodBot", pod)]:
            data = self.bots[name]
            is_alive = data['process'] and data['process'].poll() is None
            
            if on and not is_alive:
                # Cooldown check
                if time.time() - data.get('last_start_attempt', 0) < 20:
                    continue

                print(f"Supervisor: Starting {name}...")
                data['last_start_attempt'] = time.time()
                # Special naming for Recording bot handled in its script via args or env
                cmd = ["python3", data['script'], "--host", MUMBLE_HOST]
                
                try:
                    data['process'] = subprocess.Popen(cmd)
                except Exception as e:
                    print(f"Supervisor: Failed to start {name}: {e}")
                    
            elif not on and is_alive:
                print(f"Supervisor: Stopping {name}...")
                # Update kick state if it was running and we are stopping it (or it was kicked)
                # But here we are stopping it intentionally? 
                # Actually, if the process dies UNEXPECTEDLY, poll() will be not None.
                data['process'].terminate()
                data['process'] = None

    async def run(self):
        print(f"Connecting to Mumble at {MUMBLE_HOST}...")
        self.mumble = pymumble.Mumble(MUMBLE_HOST, BOT_NAME, port=64738)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.mumble_connected)
        self.mumble.start()
        
        await asyncio.to_thread(self.mumble.is_ready)
        self.mumble.set_receive_sound(True)
        print("Supervisor is running.")
        
        while self.is_running:
            if not self.mumble.is_alive():
                # Reconnect...
                break 
            
            try:
                # 1. Enforce Room
                if self.mumble.users.myself.get('channel_id') != 0:
                    self.mumble.channels[0].move_in()
                
                # 2. Check for unexpected bot exits (Kicks)
                # Need current stage humans for snapshotting
                humans, stage_humans, mic_check_humans, unverified_humans = self.get_presence_info()

                for name, data in self.bots.items():
                    if data['process'] and data['process'].poll() is not None:
                        print(f"Supervisor: {name} exited unexpectedly (Kicked?).")
                        data['process'] = None
                        data['kick_wait'] = True
                        data['kick_state_users'] = stage_humans.copy()
                        print(f"Supervisor: {name} kick snapshot: {data['kick_state_users']}")
                
                # 3. Presence Logic
                echo, rec, pod = self.get_presence_stats_from_info(humans, stage_humans, mic_check_humans, unverified_humans)
                
                # Update snapshots for kick-wait if they aren't online
                for name in ["Recording", "PodBot"]:
                    if self.bots[name]['kick_wait'] and not self.bots[name]['process']:
                        # If we haven't captured snapshot yet or to keep it updated?
                        # User says: "If kicked, it stays gone, until Jordan joins... OR until I leave and re-enter"
                        # That implies we snap at the moment of kick.
                        if 'kick_state_users' not in self.bots[name] or not self.bots[name]['kick_state_users']:
                            # This is approximate since we check 5s later, but good enough.
                            pass 

                self.manage_processes(echo, rec, pod)
                self.update_status_comment()
                
            except Exception as e:
                print(f"Supervisor Loop Error: {e}")
                
            await asyncio.sleep(5)

if __name__ == "__main__":
    bot = SupervisorBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        pass
