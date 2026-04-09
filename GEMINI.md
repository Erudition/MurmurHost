
## Pipecat Migration Constraints
- **Library**: Use `pipecat-ai` with `[google,silero]` extras for Gemini Live integration.
- **Protobuf Conflict**: Due to `pymumble` requiring Protobuf 3.x and Pipecat requiring 4.x/5.x, set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` in the environment.
- **Pymumble Installation**: Install `pymumble` from git (`https://github.com/azlux/pymumble.git`) using `--no-deps` to bypass metadata-level version conflicts.
- **Dependencies**: Manually ensure `opuslib` and `libopus-dev` are installed as they are required by `pymumble` but may be skipped during `--no-deps` install.
- **Service Type**: Use `GeminiLiveLLMService` for native multimodal support.

## Docker Log Discipline
- **Never trust stale logs.** After any `docker-compose stop/restart` of Murmur, the bot containers may still show "Up" with old logs from a previous Murmur session. Always identify the current boot boundary before interpreting logs:
  - Find the latest `Booting servers` line in the Murmur logs to determine when the current session started.
  - Use `docker logs --since <timestamp>` to only see logs from the current boot.
  - Cross-reference bot logs with the Murmur server logs to confirm the bot actually authenticated in the **current** Murmur session.
- **Verify presence server-side.** When the user reports a bot is missing, check Murmur's logs for an `Authenticated` entry in the current boot — not just the bot container's own logs, which may reflect a zombie connection.

## Pymumble Technical Notes
- **pymumble is TCP-only by design.** It tunnels audio over the TCP control channel (UDPTUNNEL message type). It has no UDP implementation (`udp_active = False`, `# TODO: use UDP audio`). Do not try to diagnose "UDP fallback" issues — they are not real.
- **Monkey-patch vs callback:** The `PYMUMBLE_CLBK_SOUNDRECEIVED` callback provides decoded PCM audio. To capture raw Opus frames (needed by `OggOpusWriter`), the `SoundQueue.add` monkey-patch is required — it intercepts the audio before decoding.
