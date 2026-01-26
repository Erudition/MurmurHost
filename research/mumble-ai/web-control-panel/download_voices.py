import os
import urllib.request

# Comprehensive list of diverse Piper TTS voices with multiple accents and styles
VOICES = [
    # === US English - Female Voices ===
    ("en_US-lessac-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"),
    ("en_US-lessac-high", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx"),
    ("en_US-amy-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx"),
    ("en_US-amy-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx"),
    ("en_US-hfc_female-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx"),
    ("en_US-kristin-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/kristin/medium/en_US-kristin-medium.onnx"),
    ("en_US-kathleen-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/kathleen/low/en_US-kathleen-low.onnx"),

    # === US English - Male Voices ===
    ("en_US-hfc_male-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx"),
    ("en_US-joe-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx"),
    ("en_US-bryce-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/bryce/medium/en_US-bryce-medium.onnx"),
    ("en_US-danny-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/danny/low/en_US-danny-low.onnx"),
    ("en_US-john-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/john/medium/en_US-john-medium.onnx"),
    ("en_US-kusal-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/kusal/medium/en_US-kusal-medium.onnx"),

    # === US English - Multi-Speaker (includes diverse accents from L2 speakers) ===
    ("en_US-l2arctic-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/l2arctic/medium/en_US-l2arctic-medium.onnx"),
    ("en_US-arctic-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/arctic/medium/en_US-arctic-medium.onnx"),
    ("en_US-libritts_r-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/libritts_r/medium/en_US-libritts_r-medium.onnx"),
    ("en_US-libritts-high", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/libritts/high/en_US-libritts-high.onnx"),

    # === British English - Female Voices ===
    ("en_GB-alba-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alba/medium/en_GB-alba-medium.onnx"),
    ("en_GB-jenny_dioco-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx"),
    ("en_GB-southern_english_female-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/southern_english_female/low/en_GB-southern_english_female-low.onnx"),

    # === British English - Male Voices ===
    ("en_GB-northern_english_male-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/northern_english_male/medium/en_GB-northern_english_male-medium.onnx"),
    ("en_GB-alan-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx"),
    ("en_GB-alan-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/en_GB-alan-medium.onnx"),

    # === British English - Regional & Multi-Speaker ===
    ("en_GB-cori-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/cori/medium/en_GB-cori-medium.onnx"),
    ("en_GB-cori-high", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/cori/high/en_GB-cori-high.onnx"),
    ("en_GB-semaine-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx"),
    ("en_GB-aru-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/aru/medium/en_GB-aru-medium.onnx"),
    ("en_GB-vctk-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/vctk/medium/en_GB-vctk-medium.onnx"),

    # === Czech ===
    ("cs_CZ-jirka-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/cs/cs_CZ/jirka/low/cs_CZ-jirka-low.onnx"),
    ("cs_CZ-jirka-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx"),

    # === Spanish - Argentina ===
    ("es_AR-daniela-high", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_AR/daniela/high/es_AR-daniela-high.onnx"),

    # === Spanish - Spain ===
    ("es_ES-carlfm-x_low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx"),
    ("es_ES-davefx-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx"),
    ("es_ES-mls_10246-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/mls_10246/low/es_ES-mls_10246-low.onnx"),
    ("es_ES-mls_9972-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/mls_9972/low/es_ES-mls_9972-low.onnx"),
    ("es_ES-sharvard-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx"),

    # === Spanish - Mexico ===
    ("es_MX-ald-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/ald/medium/es_MX-ald-medium.onnx"),
    ("es_MX-claude-high", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/claude/high/es_MX-claude-high.onnx"),

    # === Hindi - India ===
    ("hi_IN-pratham-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx"),
    ("hi_IN-priyamvada-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx"),

    # === Malayalam - India ===
    ("ml_IN-meera-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ml/ml_IN/meera/medium/ml_IN-meera-medium.onnx"),

    # === Nepali ===
    ("ne_NP-chitwan-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ne/ne_NP/chitwan/medium/ne_NP-chitwan-medium.onnx"),
    ("ne_NP-google-x_low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ne/ne_NP/google/x_low/ne_NP-google-x_low.onnx"),
    ("ne_NP-google-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ne/ne_NP/google/medium/ne_NP-google-medium.onnx"),

    # === Vietnamese ===
    ("vi_VN-25hours_single-low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/vi/vi_VN/25hours_single/low/vi_VN-25hours_single-low.onnx"),
    ("vi_VN-vais1000-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"),
    ("vi_VN-vivos-x_low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/vi/vi_VN/vivos/x_low/vi_VN-vivos-x_low.onnx"),

    # === Chinese ===
    ("zh_CN-huayan-x_low", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/x_low/zh_CN-huayan-x_low.onnx"),
    ("zh_CN-huayan-medium", "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx"),
]

def download_voice(name, url):
    """Download a voice model and its config"""
    voices_dir = "/app/piper_voices"
    os.makedirs(voices_dir, exist_ok=True)

    model_path = os.path.join(voices_dir, f"{name}.onnx")
    config_path = os.path.join(voices_dir, f"{name}.onnx.json")

    if not os.path.exists(model_path):
        print(f"Downloading {name}...")
        try:
            urllib.request.urlretrieve(url, model_path)
            print(f"  ✓ Model downloaded")

            # Download config
            config_url = url + ".json"
            urllib.request.urlretrieve(config_url, config_path)
            print(f"  ✓ Config downloaded")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print(f"  → {name} already exists")

if __name__ == "__main__":
    print("Downloading Piper TTS voices...")
    print("=" * 50)

    for name, url in VOICES:
        download_voice(name, url)

    print("=" * 50)
    print("✓ Voice download complete!")
