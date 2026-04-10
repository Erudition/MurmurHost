import asyncio
import os
import sys
import time
import docker
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
        self.docker_client = docker.from_env()
        
        # Bot Lifecycle Management
        # { name: { 'container': container_name, 'kick_state_users': set(), 'should_be_online': bool, 'kick_wait': bool, 'last_start_attempt': timestamp, 'empty_timer_start': timestamp } }
        self.bots = {
            "Echo": {"container": "echo-bot", "should_be_online": False, "kick_wait": False, "kick_state_users": set(), "last_start_attempt": 0},
            "Recording": {"container": "recording-bot", "should_be_online": False, "kick_wait": False, "kick_state_users": set(), "last_start_attempt": 0, "empty_timer_start": 0},
            "Benny Botman": {"container": "benny-bot", "should_be_online": False, "kick_wait": False, "kick_state_users": set(), "last_start_attempt": 0, "empty_timer_start": 0}
        }
        
        self.verified_users = {} # {username: timestamp_last_seen}
        self.user_mic_check_entry = {} # {username: entry_timestamp}
        
    def cleanup_zombies(self):
        """Ensures managed containers are stopped on start if they shouldn't be on."""
        print("Supervisor: Checking for lingering containers...")
        for name, data in self.bots.items():
            try:
                container = self.docker_client.containers.get(data['container'])
                if container.status == "running":
                    print(f"Supervisor: Stopping lingering container {data['container']}")
                    container.stop()
            except docker.errors.NotFound:
                pass
            except Exception as e:
                print(f"Error during cleanup of {data['container']}: {e}")

    def mumble_connected(self):
        print(f"Supervisor Connected to Mumble as {BOT_NAME}")
        
        # Enforce "Observer" State
        try:
            self.mumble.users.myself.deafen()
            self.mumble.users.myself.mute()
        except: pass
        
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.text_received)

    def mumble_disconnected(self):
        """Handle disconnect/kick - force graceful shutdown and restart."""
        print("Supervisor: Disconnected/Kicked from Mumble! Force quitting...", flush=True)
        try:
            self.graceful_shutdown()
        except Exception as e:
            print(f"Supervisor: Error during shutdown in callback: {e}", flush=True)
        finally:
            os._exit(0)  # Hard exit to ensure Docker restart immediately

    def text_received(self, msg):
        """Handle text commands for testing"""
        import re
        text = re.sub('<[^<]+?>', '', msg.message).strip()
        
        if text.startswith("!verify_user "):
            # Trusted bot reporting verification
            # Security: In a real app we'd verify the sender is Echo, but here checking name/cert is enough or loose trust
            # For now, just trust it.
            target_user = text.replace("!verify_user ", "").strip()
            print(f"Supervisor: Received verification for {target_user} from {msg.actor}")
            self.verified_users[target_user] = time.time()
            
            # Notify user - Handled by EchoBot now
            # Find user object
            pass
    



    def is_bot_alive(self, bot_data):
        try:
            container = self.docker_client.containers.get(bot_data['container'])
            return container.status == "running"
        except:
            return False

    def update_status_comment(self):
        """Updates the Supervisor's User Comment with the status of all bots and reasons."""
        report = "<b>Studio Supervisor Status</b><br/>"
        report += f"<i>Last Updated: {time.strftime('%H:%M:%S')}</i><br/><br/>"
        
        for name, data in self.bots.items():
            status = "🟢 Online" if self.is_bot_alive(data) else "🔴 Offline"
            reason = ""
            if status == "🔴 Offline":
                if name == "Echo":
                    reason = " (Waiting for humans/unverified users)"
                elif name in ["Recording", "Benny Botman"]:
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
        audience_humans = set()
        backstage_humans = set()
        hallway_humans = set()
        unverified_humans = False
        
        mc_chan = None
        st_chan = None
        au_chan = None
        bs_chan = None
        hallway_chan = None
        
        try:
            mc_chan = self.mumble.channels.find_by_name(MIC_CHECK_CHANNEL)
            st_chan = self.mumble.channels.find_by_name(TARGET_STAGE)
            au_chan = self.mumble.channels.find_by_name("Audience 👂")
            bs_chan = self.mumble.channels.find_by_name("Backstage 🤐")
        except: pass
        
        # Robust Hallway finder (startswith to handle unicode)
        for c in self.mumble.channels.values():
            try:
                name = c['name']
                if name.startswith("Hallway"):
                    hallway_chan = c
                    break
            except: pass

        for user in list(self.mumble.users.values()):
            try:
                name = user['name']
                if not name or name in [BOT_NAME, "Echo", "Benny Botman"] or name.startswith("Recording"):
                    continue
                
                humans.add(name)
                chan_id = user['channel_id']
            except: continue
            
            if st_chan and chan_id == st_chan['channel_id']:
                stage_humans.add(name)
            
            if au_chan and chan_id == au_chan['channel_id']:
                audience_humans.add(name)
                
            if bs_chan and chan_id == bs_chan['channel_id']:
                backstage_humans.add(name)
                
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

                
            # Track Hallway (Recursive Check)
            if hallway_chan:
                # Check if current channel is Hallway or a descendant
                curr = self.mumble.channels[chan_id] if chan_id in self.mumble.channels else None
                while curr:
                    if curr['channel_id'] == hallway_chan['channel_id']:
                        hallway_humans.add(name)
                        break
                    # Move up tree - safely handle root channel
                    parent_id = curr['parent'] if 'parent' in curr else None
                    curr = self.mumble.channels[parent_id] if parent_id is not None else None
        
        return humans, stage_humans, mic_check_humans, unverified_humans, audience_humans, backstage_humans, hallway_humans

    def get_presence_stats_from_info(self, humans, stage_humans, mic_check_humans, unverified_humans, audience_humans, backstage_humans, hallway_humans):
        """Calculates which bots should be on based on info sets."""
        # ECHO BOT LOGIC:
        echo_should_be_on = len(humans) > 0 and (len(mic_check_humans) > 0 or unverified_humans)
        
        # Debug Echo Logic
        if echo_should_be_on:
             print(f"DEBUG: Echo ON. Humans: {len(humans)}, MicCheck: {len(mic_check_humans)}, Unverified: {unverified_humans}")
             if unverified_humans:
                 verified_names = self.verified_users.keys()
                 unverified_names = [h for h in humans if h not in verified_names]
                 print(f"DEBUG: Unverified Users: {unverified_names}")
        
        # REC/PODBOT LOGIC:
        rec_should_be_on = self.check_presence_with_timer("Recording", stage_humans, 60)
        
        studio_humans = stage_humans | audience_humans | backstage_humans | hallway_humans
        print(f"DEBUG: Pod should be on? Studio humans: {studio_humans}")
        pod_should_be_on = self.check_presence_with_timer("Benny Botman", studio_humans, 600)
        
        return echo_should_be_on, rec_should_be_on, pod_should_be_on

    def check_presence_with_timer(self, bot_name, current_humans, timeout):
        data = self.bots[bot_name]
        is_occupied = len(current_humans) > 0
        
        # If occupied, reset timer and potentially trigger "on"
        if is_occupied:
            data['empty_timer_start'] = 0
            # Also handle kick-wait logic here
            return self.check_kick_aware_presence(bot_name, current_humans)
        else:
            # If empty, check timer
            if self.is_bot_alive(data):
                if data['empty_timer_start'] == 0:
                    data['empty_timer_start'] = time.time()
                
                elapsed = time.time() - data['empty_timer_start']
                if elapsed < timeout:
                    return True # Keep it on for now
                else:
                    return False # Leave
            else:
                return False

    def check_kick_aware_presence(self, bot_name, current_humans):
        data = self.bots[bot_name]
        
        # If container is running, we aren't in a "Kicked" state waiting for re-entry.
        if self.is_bot_alive(data):
            return True

        # If stage/studio is empty, definitely stay off.
        if len(current_humans) == 0:
            data['kick_state_users'] = set()
            return False

        # If Echo, always return based on rules (ignore kick-wait per SPEC Addendum)
        if bot_name == "Echo":
            data['kick_wait'] = False
            return True

        # If stage has people, check if we are waiting for NEW people.
        if not data.get('kick_wait', False):
            # Fresh join condition
            return True
        else:
            # We are in kick-wait. Check for positive change.
            new_people = current_humans - data.get('kick_state_users', set())
            if new_people:
                print(f"Supervisor: {bot_name} kick-wait cleared by {new_people}")
                data['kick_wait'] = False
                return True
            return False

    def manage_processes(self, echo, rec, pod):
        # Update should_be_online for status reporting
        self.bots['Echo']['should_be_online'] = echo
        self.bots['Recording']['should_be_online'] = rec
        self.bots['Benny Botman']['should_be_online'] = pod
        
        for name, on in [("Echo", echo), ("Recording", rec), ("Benny Botman", pod)]:
            data = self.bots[name]
            is_alive = self.is_bot_alive(data)
            
            if on and not is_alive:
                if time.time() - data.get('last_start_attempt', 0) < 20:
                    continue

                print(f"Supervisor: Starting container {data['container']}...")
                data['last_start_attempt'] = time.time()
                try:
                    container = self.docker_client.containers.get(data['container'])
                    container.start()
                except Exception as e:
                    print(f"Supervisor: Failed to start {name}: {e}")
                    
            elif not on and is_alive:
                print(f"Supervisor: Stopping container {data['container']}...")
                try:
                    container = self.docker_client.containers.get(data['container'])
                    container.stop()
                except Exception as e:
                    print(f"Supervisor: Failed to stop {name}: {e}")

    def graceful_shutdown(self):
        """Stop all managed containers."""
        print("Supervisor: Graceful shutdown - stopping all bots...")
        for name, data in self.bots.items():
            if self.is_bot_alive(data):
                try:
                    print(f"Supervisor: Stopping {name}...")
                    container = self.docker_client.containers.get(data['container'])
                    container.stop(timeout=5)
                except:
                    pass
        print("Supervisor: All bots stopped.")

    async def run(self):
        self.cleanup_zombies()
        print(f"Connecting to Mumble at {MUMBLE_HOST}...")
        
        # Use persistent certificate for identity
        cert_file = "/bots/certs/supervisor.pem"
        key_file = "/bots/certs/supervisor_key.pem"
        
        self.mumble = pymumble.Mumble(MUMBLE_HOST, BOT_NAME, port=64738, 
                                       certfile=cert_file, keyfile=key_file,
                                       reconnect=False)  # Disable auto-reconnect; we handle it
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.mumble_connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_DISCONNECTED, self.mumble_disconnected)
        self.mumble.start()
        
        await asyncio.to_thread(self.mumble.is_ready)
        self.mumble.set_receive_sound(True)
        print("Supervisor is running.")
        
        while self.is_running:
            if not self.mumble.is_alive():
                # Disconnected/Kicked - graceful shutdown to trigger container restart
                print("Supervisor: Disconnected from Mumble. Initiating graceful shutdown...")
                self.graceful_shutdown()
                sys.exit(0)  # Docker will restart the container
            
            try:
                # 1. Enforce Room
                # Safety: Check if 'myself' object exists and has the property
                myself = self.mumble.users.myself
                if myself and myself['channel_id'] != 0:
                    self.mumble.channels[0].move_in()
                
                # 2. Check for unexpected bot exits (Kicks)
                # Need current stage humans for snapshotting
                humans, stage_humans, mic_check_humans, unverified_humans, audience_humans, backstage_humans, hallway_humans = self.get_presence_info()

                for name, data in self.bots.items():
                    if self.is_bot_alive(data):
                        # Still running, check for unexpected exit here?
                        # Docker SDK doesn't give us a non-polling way easily in this loop.
                        pass
                    elif data.get('should_be_online') and not self.is_bot_alive(data):
                        # It should be on but isn't. Probably kicked or crashed.
                        print(f"Supervisor: {name} is offline unexpectedly (Kicked?).")
                        data['kick_wait'] = True
                        if name == "Recording":
                            data['kick_state_users'] = stage_humans.copy()
                        else:
                            data['kick_state_users'] = (stage_humans | audience_humans | backstage_humans | hallway_humans).copy()
                        print(f"Supervisor: {name} kick snapshot: {data['kick_state_users']}")
                
                # 3. Presence Logic
                echo, rec, pod = self.get_presence_stats_from_info(humans, stage_humans, mic_check_humans, unverified_humans, audience_humans, backstage_humans, hallway_humans)
                
                # Update snapshots for kick-wait if they aren't online
                for name in ["Recording", "Benny Botman"]:
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
        
        # Loop exited (is_running = False, likely from disconnect callback)
        print("Supervisor: Main loop exited. Performing graceful shutdown...", flush=True)
        self.graceful_shutdown()
        sys.exit(0)  # Docker will restart the container
            
    async def run_with_logging(self):
        try:
            await self.run()
        except Exception as e:
            print(f"FATAL SUPERVISOR ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise e

if __name__ == "__main__":
    bot = SupervisorBot()
    try:
        asyncio.run(bot.run_with_logging())
    except KeyboardInterrupt:
        pass
