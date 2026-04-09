## Recording Bot Implementation Notes
- **Monkey-patch vs callback:** The `PYMUMBLE_CLBK_SOUNDRECEIVED` callback provides decoded PCM audio. To capture raw Opus frames (needed by `OggOpusWriter`), the `SoundQueue.add` monkey-patch is required — it intercepts the audio before decoding.
- **Graceful Shutdown**: The container must handle `SIGTERM` and `SIGINT` to ensure `OggOpusWriter.finalize()` is called and WebVTT files are closed properly.
