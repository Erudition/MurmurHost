#!/bin/bash

# Download Piper TTS voice model
echo "Downloading Piper TTS voice model..."
mkdir -p models/piper
cd models/piper

if [ ! -f voice.onnx ]; then
    echo "Downloading voice.onnx (61MB)..."
    wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx -O voice.onnx
fi

if [ ! -f voice.onnx.json ]; then
    echo "Downloading voice.onnx.json..."
    wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json -O voice.onnx.json
fi

echo "✓ Piper models downloaded!"
echo ""
echo "Note: Whisper models will download automatically on first use"
