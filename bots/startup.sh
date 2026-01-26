#!/bin/bash

echo ">>> Waiting for Murmur to be ready..."
sleep 20

echo ">>> Starting Echo Bot & Manager..."
python3 /bots/echobot.py &

# Keep the script running
wait
