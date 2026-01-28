#!/bin/bash

echo ">>> Waiting for Murmur to be ready..."
sleep 20

echo ">>> Starting Echo Bot..."
python3 /bots/echobot.py &

echo ">>> Starting Recording Supervisor..."
python3 /bots/opus_recorder.py --host murmur --user "Recording" &

# Keep the script running
wait
