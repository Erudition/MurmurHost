@echo off
echo Downloading Piper TTS voice model via Docker...

docker run --rm -v "%cd%/models/piper:/models" python:3.11-slim sh -c "apt-get update && apt-get install -y wget && cd /models && wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx -O voice.onnx && wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json -O voice.onnx.json"

echo.
echo Piper models downloaded successfully!
echo.
echo Note: Whisper models will download automatically on first use
pause
