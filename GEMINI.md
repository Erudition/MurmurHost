
## Pipecat Migration Constraints
- **Library**: Use `pipecat-ai` with `[google,silero]` extras for Gemini Live integration.
- **Protobuf Conflict**: Due to `pymumble` requiring Protobuf 3.x and Pipecat requiring 4.x/5.x, set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` in the environment.
- **Pymumble Installation**: Install `pymumble` from git (`https://github.com/azlux/pymumble.git`) using `--no-deps` to bypass metadata-level version conflicts.
- **Dependencies**: Manually ensure `opuslib` and `libopus-dev` are installed as they are required by `pymumble` but may be skipped during `--no-deps` install.
- **Service Type**: Use `GeminiLiveLLMService` for native multimodal support.

## Mumble Bot Audio Constraints
- **Mute vs Suppression**: Mumble servers handle "Server Mute" (suppression) independently of "Self Mute". If a bot joins a suppressed channel (e.g. Root) with self-mute disabled (the default for pymumble), it will be automatically suppressed by the server. Moving to a non-suppressed channel (e.g. Mic Check) restores audio output without requiring an explicit `unmute()` call. Maintenance code should NOT call `unmute()` redundantly.

## Pymumble & Library Constraints
- **Attribute Access**: Pymumble `User` and `Channel` objects inherit from `dict` but overload `update()`. They **DO NOT** reliably support `.get()`. Always use direct dictionary access `obj['key']` inside a `try...except` block or use `getattr()` with care.
- **Initialization Race**: `self.mumble.users.myself` is `None` upon instantiation. It is only populated after the `SERVERSYNC` message. Always wait for `mumble.is_ready()` and check if `myself` is not None before accessing its properties.
- **Audio Initialization**: `mumble.set_receive_sound(True)` **MUST** be called BEFORE `mumble.start()`. If called after, the `SoundOutput` manager will not be initialized, and audio callbacks will fail with a `NoneType` error when attempting to add sound.
- **Parrot Mode (Echo Bot)**:
    - **Resolution**: Use a 10ms main loop sleep for near-instant VAD response.
    - **VAD Hang-time**: 80ms is used to distinguish network jitter from the end of transmission.
    - **Interruption**: Use `mumble.sound_output.clear_buffer()` to immediately silence the bot when a human resumes speaking.

## Docker & Lifecycle Constraints
- **Thread Management**: Pymumble threads cannot be restarted once stopped (`RuntimeError`). Bots must use `sys.exit(1)` on connection loss to allow Docker to manage the process lifecycle.
- **Restart Policies**: Use `restart: unless-stopped` for the **Supervisor** only. Bots managed by the Supervisor (like Echo) must use `restart: "no"` to prevent conflicting restart loops and "zombie" processes.
- **Mandatory Rebuilds**: These bot containers do NOT use host volume mounts for source code. Any changes to `.py` files **REQUIRE** a `docker compose build <service>` followed by `docker compose up -d` to take effect.
