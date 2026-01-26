#!/bin/bash

echo ">>> Waiting for Murmur to be ready..."
sleep 10

echo ">>> Starting Echo Bot..."
python3 /bots/echobot.py &

echo ">>> Starting Mumo (Mumble Moderator)..."
cd /bots/mumo
python3 mumo.py -a &

echo ">>> Starting Opus Recorder Bot..."
python3 /bots/opus_recorder.py --host murmur --user RecorderBot &

# Keep the script running
wait
