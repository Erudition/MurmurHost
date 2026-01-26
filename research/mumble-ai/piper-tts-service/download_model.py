import os
import urllib.request

# Download a default English voice model
model_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
config_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

model_dir = "/app/models"
os.makedirs(model_dir, exist_ok=True)

model_path = os.path.join(model_dir, "voice.onnx")
config_path = os.path.join(model_dir, "voice.onnx.json")

if not os.path.exists(model_path):
    print("Downloading voice model...")
    urllib.request.urlretrieve(model_url, model_path)
    print("Model downloaded")

if not os.path.exists(config_path):
    print("Downloading model config...")
    urllib.request.urlretrieve(config_url, config_path)
    print("Config downloaded")
