
## Pipecat Migration Constraints
- **Library**: Use `pipecat-ai` with `[google,silero]` extras for Gemini Live integration.
- **Protobuf Conflict**: Due to `pymumble` requiring Protobuf 3.x and Pipecat requiring 4.x/5.x, set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` in the environment.
- **Pymumble Installation**: Install `pymumble` from git (`https://github.com/azlux/pymumble.git`) using `--no-deps` to bypass metadata-level version conflicts.
- **Dependencies**: Manually ensure `opuslib` and `libopus-dev` are installed as they are required by `pymumble` but may be skipped during `--no-deps` install.
- **Service Type**: Use `GeminiLiveLLMService` for native multimodal support.

## Mumble Bot Audio Constraints
- **Mute vs Suppression**: Mumble servers handle "Server Mute" (suppression) independently of "Self Mute". If a bot joins a suppressed channel (e.g. Root) with self-mute disabled (the default for pymumble), it will be automatically suppressed by the server. Moving to a non-suppressed channel (e.g. Mic Check) restores audio output without requiring an explicit `unmute()` call. Maintenance code should NOT call `unmute()` redundantly.
