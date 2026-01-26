#!/usr/bin/python3
# This bot sends any sound it receives back to where it has come from.
# WARNING! Don't put two bots in the same place!

# connor: https://github.com/azlux/pymumble/blob/pymumble_py3/API.md#channels-object

import pymumble_py3
import time
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED as PCS

pwd = ""  # password
server = "murmur"
nick = "Echo"


def sound_received_handler(user, soundchunk):
    # sending the received sound back to server
    mumble.sound_output.add_sound(soundchunk.pcm)


mumble = pymumble_py3.Mumble(server, nick, password=pwd)
mumble.callbacks.set_callback(PCS, sound_received_handler)
mumble.set_receive_sound(1)  # we want to receive sound
mumble.start()
mumble.is_ready()
try:
    target = mumble.channels.find_by_name("Mic Check")
    target.move_in()
except:
    print("Mic Check channel not found, remaining in root.")
print(mumble.channels)
print(mumble.users)
#mumble.users[6].recording()

while 1:
    time.sleep(1)
