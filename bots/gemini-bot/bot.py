import asyncio
import os
import sys
import threading
import time
import audioop # LESSON LEARNED: audioop is available in 3.11 but deprecated in later versions. 
               # It's used here for simple resampling without heavy dependencies.
import numpy as np
import pymumble_py3 as pymumble
from pymumble_py3.constants import *
from google import genai
from google.genai import types

# REQUESTED INVARIANTS
GEMINI_API_KEY = "AIzaSyA_Yjb6fnN0FkFEIIXUc7hh-CXVXYmkB9c"
MUMBLE_HOST = os.getenv("MUMBLE_HOST", "murmur")
BOT_NAME = "PodBot"
AUDIENCE_CHANNEL = "Audience 👂"
ECHO_BOT_NAME = "Echo"
VOICE_NAME = "Charon"  # REQUESTED INVARIANT: Deep male voice

# System Instructions
SYSTEM_INSTRUCTION = (
    "You are a 'Podcast sidekick'. The hosts are Connor and Jordan. "
    "Your goal is to be a helpful, witty, and engaging assistant during the podcast. "
    "You will receive audio from the Mumble server. We will inform you who is currently producing audio with text tags like [Speaker: Name]. "
    "CRITICAL: The [Speaker: Name] tag is metadata. DO NOT echo it or repeat it in your response. "
    "Use the name inside the tag to address the speaker (e.g., 'Hey Connor...'). "
    "Your response will be heard by everyone in the room as voice audio, UNLESS you are informed that you are 'SUPPRESSED'. "
    "If you are SUPPRESSED, the server has blocked your voice. In this state, you should still process audio you hear, but respond via text chat using the 'send_channel_message' tool. "
    "You have tools available to send messages, move channels, and manage your own mute state."
)

class MumbleGeminiBot:
    def __init__(self):
        self.mumble = None
        self.client = genai.Client(
            api_key=GEMINI_API_KEY, 
            http_options={'api_version': 'v1alpha'}
        )
        # REQUESTED INVARIANT: Robust buffering for Gemini drops. 
        # Using a large queue size to prevent loss during brief reconnects.
        self.to_gemini_queue = asyncio.Queue(maxsize=2000) 
        self.loop = None
        self.current_speaker = None
        self.is_running = True
        self.gemini_session = None
        self.humans_present = False
        self.human_names = set()
        self.is_suppressed = False
        self.last_gemini_conn_time = time.time()
        self.current_channel_id = None
        
    def send_context(self, text):
        """Sends a text turn to Gemini for real-time context."""
        print(f"Context update: {text}")
        try:
            self.loop.call_soon_threadsafe(self.to_gemini_queue.put_nowait, f"[System: {text}]")
        except: pass

    def mumble_connected(self):
        print(f"Connected to Mumble as {BOT_NAME}")
        self.mumble.users.myself.comment("Gemini AI Sidekick")
        
        # Initial humans check (careful, could be blocking)
        self.update_humans()
        
        # Set initial state
        self.current_channel_id = self.mumble.users.myself.get('channel_id')
        self.check_suppression(self.mumble.users.myself)
        
        # Set up real-time callbacks
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_USERUPDATED, self.user_updated)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_USERREMOVED, self.user_removed)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CHANNELUPDATED, self.channel_updated)
        
    def update_humans(self):
        """Updates the list of humans present on the server."""
        try:
            all_users = list(self.mumble.users.values())
            humans = [u.get('name') for u in all_users if u.get('name') not in [BOT_NAME, ECHO_BOT_NAME, "Recording"]]
            self.human_names = set(filter(None, humans))
            self.humans_present = len(self.human_names) > 0
        except:
            pass

    def user_updated(self, user, updated):
        """Handles user state changes (join, move, mute, etc.)"""
        self.update_humans()
        my_id = self.mumble.users.myself.get('session')
        if user.get('session') == my_id:
            # Self update
            if 'channel_id' in updated:
                new_chan = self.mumble.channels.get(updated['channel_id'])
                self.current_channel_id = updated['channel_id']
                members = [u.get('name') for u in self.mumble.users.values() if u.get('channel_id') == self.current_channel_id and u.get('session') != my_id]
                self.send_context(f"You moved to channel '{new_chan.get('name') if new_chan else 'Unknown'}'. Other members: {', '.join(filter(None, members)) if members else 'None'}")
                # Check suppression immediately on move
                self.check_suppression(user)
            
            if 'mute' in updated or 'suppressed' in updated or 'self_mute' in updated:
                self.check_suppression(user)
        else:
            # Other user update
            if 'channel_id' in updated:
                if updated['channel_id'] == self.current_channel_id:
                    self.send_context(f"User {user.get('name')} joined your channel.")
                elif user.get('old_channel_id') == self.current_channel_id:
                    self.send_context(f"User {user.get('name')} left your channel.")

    def user_removed(self, user):
        """Handles user disconnection"""
        self.update_humans()
        if user.get('channel_id') == self.current_channel_id:
            self.send_context(f"User {user.get('name')} disconnected.")

    def channel_updated(self, channel, updated):
        pass # Could track channel name changes etc.

    def check_suppression(self, user):
        """Updates suppression state and informs Gemini if it changes"""
        # In Mumble, 'mute' or 'suppressed' usually means the server is blocking output.
        suppressed = user.get('mute', False) or user.get('suppressed', False)
        if suppressed != self.is_suppressed:
            self.is_suppressed = suppressed
            state = "SUPPRESSED (Voice blocked by server)" if suppressed else "UNSUPPRESSED (Voice enabled)"
            self.send_context(f"You are now {state}")

    def sound_received(self, user, sound):
        if not self.gemini_session:
            # We still buffer even if Gemini is temporarily down, 
            # but maybe not if we haven't started at all.
            # Actually, the user asked for buffering when API connection drops.
            if not self.humans_present:
                return

        username = user.get('name')
        if not username:
            return
        
        # Speaker identification
        if self.current_speaker != username:
            self.current_speaker = username
            msg = f"[Speaker: {username}]"
            try:
                self.loop.call_soon_threadsafe(self.to_gemini_queue.put_nowait, msg)
            except asyncio.QueueFull:
                pass

        # Resample 48000 -> 16000
        try:
            # sound.pcm is 16-bit mono 48k
            resampled, _ = audioop.ratecv(sound.pcm, 2, 1, 48000, 16000, None)
            self.loop.call_soon_threadsafe(self.to_gemini_queue.put_nowait, resampled)
        except Exception as e:
            pass

    async def run_gemini_loop(self):
        model_id = "gemini-2.0-flash-exp"
        config = {
            "generation_config": {
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": VOICE_NAME}
                    }
                }
            },
            "system_instruction": SYSTEM_INSTRUCTION,
            "tools": [{
                "function_declarations": [
                    {
                        "name": "send_channel_message",
                        "description": "Send a message to the current channel.",
                        "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}
                    },
                    {
                        "name": "send_private_message",
                        "description": "Send a direct message to a specific user.",
                        "parameters": {"type": "object", "properties": {"user_name": {"type": "string"}, "message": {"type": "string"}}, "required": ["user_name", "message"]}
                    },
                    {
                        "name": "move_to_channel",
                        "description": "Move yourself to another channel. Cannot move to a channel containing the Echo Bot.",
                        "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}}, "required": ["channel_name"]}
                    },
                    {
                        "name": "unmute_myself",
                        "description": "Ensure the bot is not self-muted or suppressed in Mumble.",
                        "parameters": {"type": "object", "properties": {}}
                    }
                ]
            }]
        }

        while self.is_running:
            if not self.humans_present:
                # Clear queue if no humans, to avoid stale audio
                while not self.to_gemini_queue.empty():
                    self.to_gemini_queue.get_nowait()
                await asyncio.sleep(2)
                continue

            print(f"Connecting to Gemini Live API with model {model_id}...")
            try:
                # Modernize config: move generation_config fields directly to LiveConnectConfig
                connect_config = {
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": VOICE_NAME}
                        }
                    },
                    "system_instruction": SYSTEM_INSTRUCTION,
                    "tools": config["tools"]
                }
                
                async with self.client.aio.live.connect(model=model_id, config=connect_config) as session:
                    self.gemini_session = session
                    self.last_gemini_conn_time = time.time()
                    print("Gemini session established.")
                    
                    # Visually indicate we are hearing
                    self.mumble.users.myself.self_deaf = False
                    
                    async def sender():
                        print("Sender task started.")
                        # Clear stale audio on connection if it was down for > 10s
                        if time.time() - self.last_gemini_conn_time > 10:
                            print("Connection was down for > 10s. Flushing stale audio queue.")
                            while not self.to_gemini_queue.empty():
                                self.to_gemini_queue.get_nowait()
                            
                        self.last_gemini_conn_time = time.time()
                        while self.gemini_session == session:
                            item = await self.to_gemini_queue.get()
                            try:
                                if isinstance(item, str):
                                    print(f"Sending text to Gemini: {item}")
                                    # Use keyword arguments to avoid positional argument errors in v1alpha
                                    await session.send(input=item, end_of_turn=False)
                                else:
                                    # audio data
                                    await session.send(input={"data": item, "mime_type": "audio/pcm;rate=16000"}, end_of_turn=False)
                            except Exception as e:
                                print(f"Sender error: {e}")
                                break

                    async def receiver():
                        print("Receiver task started.")
                        try:
                            # session.receive() returns an async iterator in this version
                            async for message in session.receive():
                                if not message:
                                    continue
                                
                                if message.server_content and message.server_content.model_turn:
                                    parts = message.server_content.model_turn.parts
                                    if parts:
                                        for part in parts:
                                            if part.inline_data:
                                                if self.is_suppressed:
                                                    # Do not output sound if suppressed
                                                    continue
                                                try:
                                                    resampled, _ = audioop.ratecv(part.inline_data.data, 2, 1, 24000, 48000, None)
                                                    self.mumble.sound_output.add_sound(resampled)
                                                except Exception as e:
                                                    print(f"Receiver audio error: {e}")
                                            elif part.text:
                                                print(f"Model text: {part.text}")
                                    
                                if message.tool_call:
                                    print(f"Received tool call: {message.tool_call}")
                                    for call in message.tool_call.function_calls:
                                        res = await self.handle_tool_call(call)
                                        await session.send(types.LiveClientToolResponse(
                                            function_responses=[types.FunctionResponse(
                                                name=call.name,
                                                id=call.id,
                                                response=res
                                            )]
                                        ))
                        except Exception as e:
                            print(f"Receiver loop exception: {e}")

                    await asyncio.gather(sender(), receiver())
            except Exception as e:
                print(f"Gemini connection error: {e}")
                self.gemini_session = None
                # Visually indicate we are disconnected/not hearing
                try:
                    self.mumble.users.myself.self_deaf = True
                except: pass
                await asyncio.sleep(5)

    async def handle_tool_call(self, call):
        name = call.name
        args = call.args
        print(f"Executing tool: {name} with args {args}")
        try:
            if name == "send_channel_message":
                chan_id = self.mumble.users.myself.get('channel_id')
                chan = self.mumble.channels.get(chan_id)
                if chan:
                    chan.send_text_message(args['message'])
                    return {"status": "success"}
                return {"error": "Channel not found"}
            elif name == "send_private_message":
                user = self.mumble.users.find_by_name(args['user_name'])
                if user:
                    user.send_text_message(args['message'])
                    return {"status": "success"}
                return {"error": f"User '{args['user_name']}' not found"}
            elif name == "move_to_channel":
                target = self.mumble.channels.find_by_name(args['channel_name'])
                if not target:
                    return {"error": f"Channel '{args['channel_name']}' not found"}
                
                # Check for Echo bot in target channel
                for u in self.mumble.users.values():
                    if u.get('name') == ECHO_BOT_NAME and u.get('channel_id') == target.get('channel_id'):
                        return {"error": "Cannot move to a channel containing the Echo Bot"}
                        
                self.mumble.channels[target.get('channel_id')].move_in()
                return {"status": "success"}
            elif name == "unmute_myself":
                self.mumble.users.myself.unmute()
                self.mumble.users.myself.undeaf()
                self.mumble.users.myself.self_mute = False
                self.mumble.users.myself.self_deaf = False
                return {"status": "success", "message": "Bot unmuted and undeafened."}
        except Exception as e:
            return {"error": str(e)}
        return {"error": "Function not implemented"}

    async def main_loop(self):
        self.loop = asyncio.get_running_loop()
        
        print(f"Connecting to Mumble at {MUMBLE_HOST}...")
        self.mumble = pymumble.Mumble(MUMBLE_HOST, BOT_NAME, port=64738, reconnect=True)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_CONNECTED, self.mumble_connected)
        self.mumble.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self.sound_received)
        self.mumble.start()
        
        print("Waiting for Mumble to be ready (blocking call)...", flush=True)
        await asyncio.to_thread(self.mumble.is_ready)
        
        print("Mumble is ready. Setting up audio...", flush=True)
        self.mumble.set_receive_sound(True)
        
        print("Starting Gemini loop task...", flush=True)
        self.gemini_task = asyncio.create_task(self.run_gemini_loop())
        
        print("Entering main state monitoring loop...", flush=True)
        
        while self.is_running:
            try:
                print(f"MAIN LOOP TICK | Humans: {self.humans_present} ({list(self.human_names)})", flush=True)
                
                my_user = self.mumble.users.myself
                my_chan_id = my_user.get('channel_id')

                if self.humans_present:
                    if my_chan_id == 0:
                        target = self.mumble.channels.find_by_name(AUDIENCE_CHANNEL)
                        if target:
                            print(f"Auto-moving to {AUDIENCE_CHANNEL}", flush=True)
                            self.mumble.channels[target.get('channel_id')].move_in()
                else:
                    if my_chan_id != 0:
                        print("No humans, returning to root", flush=True)
                        self.mumble.channels[0].move_in()
            except Exception as e:
                print(f"Main Loop Error: {e}", flush=True)
                
            await asyncio.sleep(5)

if __name__ == "__main__":
    bot = MumbleGeminiBot()
    try:
        asyncio.run(bot.main_loop())
    except KeyboardInterrupt:
        pass
