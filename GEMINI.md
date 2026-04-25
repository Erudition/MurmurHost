
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
- **pymumble is TCP-only by design.** It tunnels audio over the TCP control channel (UDPTUNNEL message type). It has no UDP implementation (`udp_active = False`, `# TODO: use UDP audio`).

## Mumble ACL Notes
- **Linked-channel audio requires Speak in the destination.** When channels are linked, Murmur checks whether the speaker has `Speak` permission in each *destination* channel before forwarding audio there. If the Root channel denies `Speak` for `@all`, linked audio will be silently dropped unless the destination channel explicitly overrides it.
- **Use `@out` to allow linked audio without allowing local speech.** To keep a channel listen-only (e.g. Audience) while still receiving linked audio from another channel (e.g. Stage), grant `Speak` to `@out` on the listen-only channel. Users physically *in* the channel (`@in`) remain muted; only users *outside* (`@out`, i.e. the linked speakers) get the grant.
- **ACL evaluation is per-channel, bottom-up.** Rules on a specific channel override inherited rules from parents. Priority ordering within a channel matters — higher priority rules are evaluated last and take precedence.
- **Permission bitmask reference:** Write=1, Traverse=2, Enter=4, Speak=8, Whisper=16, Move=32, MakeChannel=64, LinkChannel=128, AltSpeak=256, TextMessage=512, MakeTempChannel=1024, Listen=2048.

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

## Total Interactive Convergence — Definitive Success (2026-04-17)

The interactive lock was achieved by aligning the protocol, signal, and delivery layers into a "Perfect Connection" state using the Native Google GenAI SDK (v1beta).

### Final Breakthrough Stack (v14)
- **Protocol (Single-Session)**: **NEVER RESET THE SESSION**. The Gemini Live API maintains conversational context within a single WebSocket connection. Resetting the session on `turn_complete` causes amnesia and voice inconsistency.
- **SDK Signatures (Targeted)**:
  - **Audio Fragments**: Use `session.send_realtime_input(audio=types.Blob(...))`. Do NOT use `media_chunks`.
  - **Tool Responses**: Use `session.send_tool_response(function_responses=[...])`. The generic `send()` with `tool_response` keyword will crash the session in modern SDK versions.
  - **Turn Switch**: Use `session.send_realtime_input(audio_stream_end=True)` to signal model processing.
- **Signal Integrity**: **Unity Gain (1.0x)** mandatory in `MumbleTransport` to prevent VAD clipping.
- **Phonetic Heartbeat**: Proactively send a 200ms silence block (`b'\x00' * 3200`) after `send_tool_response` to maintain turn sensitivity.
- **Lifecycle Alignment**: `presence_manager` must gate the audio uplink until the bot is undeafened and moved into the target channel.

### Stability Constants
- **VAD Watchdog**: 1.0s silence threshold is the optimal balance between turn-switching and phonetic tail preservation for tool-use.
- **Model**: `gemini-3.1-flash-live-preview` (multimodal native audio).
- **Environment**: `PYTHONUNBUFFERED=1` and `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`.

## Local Testing & Git Discipline
- **Mandatory Local Verification**: DO NOT push code to the remote repository unless it has been verified locally first. This includes:
    - Syntax validation (e.g., `python3 -m py_compile` or `bash -n`).
    - Local container test runs for Docker/Compose changes.
    - Integration testing of external library signatures (e.g., PyMumble) against the local environment.
- **Zero-Tolerance for Trial-and-Error Commits**: Avoid iterative "fixing in production" commits. All logic must be proven sound before it ever hits the main branch.
