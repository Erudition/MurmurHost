import asyncio

def get_tools_definition():
    """Returns the list of tool function declarations for Gemini Live API."""
    return [
        {
            "function_declarations": [
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
            ]
        }
    ]

async def dispatch_tool_call(bot, call):
    """
    Executes the tool call logic and returns the result string.
    
    Args:
        bot: The bot instance (must have self.mumble and self.bot_name)
        call: The tool call object with 'name' and 'args'
    """
    name = call.name
    args = call.args
    bot.log(f"Executing Tool: {name}({args})")
    
    result = "Success"
    try:
        if name == "mute_self":
            bot.mumble.users.myself.mute()
        elif name == "unmute_self":
            bot.mumble.users.myself.unmute()
        elif name == "change_room":
            target = bot.mumble.channels.find_by_name(args["channel_name"])
            if target:
                bot.mumble.channels[target["channel_id"]].move_in()
            else:
                result = f"Error: Channel {args['channel_name']} not found."
        elif name == "send_room_message":
            chan = bot.mumble.channels.get(bot.mumble.users.myself['channel_id'])
            chan.send_text_message(f"<b>{bot.bot_name}:</b> {args['message']}")
        elif name == "send_direct_message":
            target_user = None
            for u in bot.mumble.users.values():
                if u['name'] == args['username']:
                    target_user = u
                    break
            if target_user:
                target_user.send_text_message(f"<b>(Private) {bot.bot_name}:</b> {args['message']}")
            else:
                result = f"Error: User {args['username']} not found."
        else:
            result = f"Error: Tool {name} not implemented."
    except Exception as e:
        result = f"Error: {e}"
        
    return result
