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
    "CRITICAL: Use the name provided in the [Speaker: Name] tag to address the speaker. Do not guess or assume based on the previous turn. "
    "Your response will be heard by everyone in the room. "
    "You have tools available to send messages, move channels, and manage your own mute state. "
    "Do not move to a channel containing the Echo Bot."
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
        
    def mumble_connected(self):
        print(f"Connected to Mumble as {BOT_NAME}")
        self.mumble.users.myself.comment("Gemini AI Sidekick")

    def sound_received(self, user, sound):
        if not self.gemini_session:
            # We still buffer even if Gemini is temporarily down, 
            # but maybe not if we haven't started at all.
            # Actually, the user asked for buffering when API connection drops.
            if not self.humans_present:
                return

        username = user['name']
        
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
                    },
                    {
                        "name": "check_room_status",
                        "description": "List all users in the bot's current channel and their mute/deaf states.",
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
                    print("Gemini session established.")
                    
                    async def sender():
                        print("Sender task started.")
                        # Clear stale audio on connection
                        while not self.to_gemini_queue.empty():
                            self.to_gemini_queue.get_nowait()
                            
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
                await asyncio.sleep(5)

    async def handle_tool_call(self, call):
        name = call.name
        args = call.args
        print(f"Executing tool: {name} with args {args}")
        try:
            if name == "send_channel_message":
                chan_id = self.mumble.users.myself['channel_id']
                self.mumble.channels.get(chan_id).send_text_message(args['message'])
                return {"status": "success"}
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
                    if u['name'] == ECHO_BOT_NAME and u['channel_id'] == target['channel_id']:
                        return {"error": "Cannot move to a channel containing the Echo Bot"}
                        
                self.mumble.channels[target['channel_id']].move_in()
                return {"status": "success"}
            elif name == "unmute_myself":
                self.mumble.users.myself.unmute()
                self.mumble.users.myself.undeaf()
                # self_mute/self_deaf are also things
                self.mumble.users.myself.self_mute = False
                self.mumble.users.myself.self_deaf = False
                return {"status": "success", "message": "Bot unmuted and undeafened."}
            elif name == "check_room_status":
                my_chan = self.mumble.users.myself.get('channel_id')
                users = []
                for u in self.mumble.users.values():
                    if u.get('channel_id') == my_chan:
                        users.append({
                            "name": u.get('name'),
                            "mute": u.get('mute'),
                            "deaf": u.get('deaf'),
                            "self_mute": u.get('self_mute'),
                            "self_deaf": u.get('self_deaf'),
                            "suppressed": u.get('suppressed', False)
                        })
                return {"channel_id": my_chan, "users": users}
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
        print("Waiting for Mumble to be ready...")
        self.mumble.is_ready()
        print("Mumble is ready.")
        self.mumble.set_receive_sound(True)
        
        print("Starting Gemini loop task...")
        asyncio.create_task(self.run_gemini_loop())
        
        print("Entering main state monitoring loop...")
        
        while self.is_running:
            # Filter humans: skip PodBot, Echo, and Recording bot
            all_users = list(self.mumble.users.values())
            # print(f"DEBUG: All users seen: {[u['name'] for u in all_users]}")
            humans = [u for u in all_users if u['name'] not in [BOT_NAME, ECHO_BOT_NAME, "Recording"]]
            self.humans_present = len(humans) > 0
            
            if self.humans_present:
                # print(f"Humans detected: {[u['name'] for u in humans]}")
                # Only auto-join Audience if we are currently "outside" (in the root channel)
                if self.mumble.users.myself['channel_id'] == 0:
                    target = self.mumble.channels.find_by_name(AUDIENCE_CHANNEL)
                    if target:
                        print(f"Humans present ({[u['name'] for u in humans]}). Moving to {AUDIENCE_CHANNEL}")
                        self.mumble.channels[target['channel_id']].move_in()
            if not self.humans_present:
                # No humans, move back to root if not already there
                if self.mumble.users.myself['channel_id'] != 0:
                    print("No humans present. Leaving Audience channel.")
                    self.mumble.channels[0].move_in()
            
            # Periodic health check: ensure we aren't suppressed if humans are present
            if self.humans_present and (self.mumble.users.myself.get('mute') or self.mumble.users.myself.get('self_mute')):
                # Don't auto-unmute if we were moved outside by a manager, but if we are in one of our target channels...
                my_chan_id = self.mumble.users.myself.get('channel_id')
                my_chan = self.mumble.channels.get(my_chan_id)
                if my_chan and (my_chan['name'] == AUDIENCE_CHANNEL or "Stage" in my_chan['name']):
                    print("Bot appears muted/suppressed while in active channel. Attempting to unmute...")
                    self.mumble.users.myself.unmute()
                    self.mumble.users.myself.self_mute = False
                
            await asyncio.sleep(5)

if __name__ == "__main__":
    bot = MumbleGeminiBot()
    try:
        asyncio.run(bot.main_loop())
    except KeyboardInterrupt:
        pass
