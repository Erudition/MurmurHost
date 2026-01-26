# Mumble Bot Research & Analysis

## [Prior99/mumble-bot](https://github.com/Prior99/mumble-bot)
- **Status**: ⚠️ Abandonware (Last update: March 2019)
- **Tech Stack**: Node.js (TypeScript), PostgreSQL, React (Web UI).
- **Capabilities**:
    - **Soundboard**: Excellent Web UI for managing and playing sounds.
    - **Recording**: Supports multi-track recording via FFmpeg.
- **Analysis**:
    - **Pros**: Polished Web UI, stable soundboard functionality.
    - **Cons**: Recording re-encodes to 128kbps MP3 and slices files on silence, which is suboptimal for professional podcasting. Uses an older Node.js version (v12).
- **Verdict**: Use for the **Web UI and Soundboard**, but skip for high-quality recording.

---

## [okabsd/stumble](https://github.com/okabsd/stumble)
- **Status**: ✅ Active-ish (Modern dependencies, modular)
- **Tech Stack**: Node.js, `fluent-ffmpeg`.
- **Capabilities**:
    - **Extensible**: Highly modular framework for Mumble bots.
    - **Sound Management**: Basic soundboard features, YouTube streaming.
- **Analysis**:
    - **Recording**: No native recording feature found. Uses `ffmpeg` for playback/streaming.
- **Verdict**: Good for utility, but lacks the core recording requirement.

---

## [DuckBoss/JJMumbleBot](https://github.com/DuckBoss/JJMumbleBot)
- **Status**: ⚠️ Maintenance/Legacy (Reworking into Mumimo)
- **Tech Stack**: Python 3.9+, `pymumble`.
- **Capabilities**:
    - **Feature Rich**: Large plugin ecosystem, web interface, soundboard.
- **Analysis**:
    - **Recording**: No explicit recording features in the code.
- **Verdict**: Powerful soundboard bot, but not a recorder.

---

## [DuckBoss/Mumimo](https://github.com/DuckBoss/Mumimo)
- **Status**: 🛑 Under Construction
- **Verdict**: Explicitly marked as not ready for use.

---

## [bkacjios/lua-mumble](https://github.com/bkacjios/lua-mumble)
- **Status**: ✅ Active
- **Tech Stack**: Lua, C, `libopus`, `libsndfile`.
- **Capabilities**:
    - **C Bindings**: Provides raw access to Mumble client features.
    - **Recording**: Supports `user:startRecord()`.
- **Analysis**:
    - **Recording**: Writing to OGG/Vorbis via `libsndfile` (`SF_FORMAT_OGG | SF_FORMAT_VORBIS`). This re-encodes the stream.
- **Verdict**: Interesting for C-level integration, but still re-encodes audio.

---

## [chartmann1590/Mumble-AI](https://github.com/chartmann1590/Mumble-AI)
- **Status**: ✅ Heavily Active (Advanced AI Ecosystem)
- **Tech Stack**: Python, Docker, Ollama, Whisper, TTS.
- **Capabilities**: Full AI assistant with STT/TTS and memory.
- **Analysis**:
    - **Recording**: Processes audio for AI tasks (STT) but lacks a dedicated continuous multi-track "podcast" recording mode.
- **Verdict**: Overkill for recording; highly specialized for AI interaction.

---

## [codeandkey/bigbot](https://github.com/codeandkey/bigbot)
- **Status**: ✅ Active
- **Tech Stack**: Rust, `tokio`, `opus`.
- **Capabilities**: High-performance Rust bot focused on sound management and effects.
- **Analysis**:
    - **Recording**: No recording implementation found. Focused on efficient playback.
- **Verdict**: Great performance for soundboard, but no recorder.