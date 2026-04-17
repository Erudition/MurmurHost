
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

## Gemini Bot Audio Debugging — Ruled-Out Causes (2026-04-10)

The Gemini bot ("Benny Botman") joins the Mumble channel, unmutes, and establishes a WebSocket to Gemini Live, but produces no audio response. The following root causes have been **exhaustively ruled out** via instrumented diagnostic runs:

### Transport & Event Loop
- **Event loop identity**: `asyncio.get_event_loop()` inside `async def main()` returns the same object as `asyncio.get_running_loop()`. The loop reference captured by `MumbleInputTransport` is correct.
- **`_input_ready` gate**: Confirmed `True` when sound callbacks fire.
- **`_loop` reference**: Confirmed valid (non-None) when sound callbacks fire.
- **`_paused` state**: Initialized `False` in `BaseInputTransport.__init__`. Only set `True` by `pause()`, which is never called. Not blocking audio.

### Pipecat Pipeline Configuration
- **`audio_in_enabled`**: Set to `True` in `TransportParams`. Confirmed not blocking `push_audio_frame`.
- **`audio_in_passthrough`**: Set to `True` in `TransportParams`. This is the code path that causes `_audio_task_handler` to call `push_frame()` directly.
- **`push_audio_frame` exceptions**: Done-callbacks on all `run_coroutine_threadsafe` futures showed **zero errors**. Frames are successfully enqueued into `_audio_in_queue`.
- **LLMRunFrame bootstrap**: `LLMRunFrame` is queued on pipeline start to initialize the Gemini multimodal session. FrameLogger confirms `StartFrame` passes through.

### Callback Registration
- **SOUNDRECEIVED callback**: Confirmed firing. Instrumentation logged exactly 5 invocations, each with `pcm_len=1920` (20ms of 48kHz mono PCM). The callback, resampling, gain boost, and queue push all execute correctly.

### Mute State
- **Bot self-mute**: Tester confirms Benny is unmuted before sending audio. Not the issue.

### Active Hypothesis: Mumble-Level Audio Transmission Deficit
- **Observation**: Only **5 audio frames (~100ms)** were received by Benny's pymumble instance. A 13.8KiB opus clip decoded to 48kHz PCM should produce **~100+ frames (~2+ seconds)**. The loss is 95%+.
- **Implication**: The Pipecat pipeline is working correctly — it faithfully processes the 5 frames it receives. But ~100ms of audio is far below any VAD threshold and insufficient for Gemini to produce a response.
- **Next investigation**: Why the tester's `mumble.sound_output.add_sound()` transmissions are not reaching Benny. Possible causes: pymumble send-thread not flushing its buffer before the tester exits, Mumble server packet dropping, or an encoding issue on the tester side.

## Total Interactive Convergence — Definitive Success (2026-04-12)

The interactive lock was achieved by aligning the protocol, signal, and delivery layers into a "Perfect Connection" state.

### Final Breakthrough Stack
- **Protocol (Uplink)**: Standardized on `v1beta` using a **Single-Call Unified Uplink**. The SDK call must use the explicit `audio=` keyword: `send_realtime_input(audio=...)`.
- **Explicit Turn-Switch**: Server-side VAD in `v1beta` is unreliable for low-latency turns. The bot sends `audio_stream_end=True` after a 500ms silence flush to force the model from "Listening" to "Generating" state.
- **Signal Purity**: **Unity Gain (1.0x)** is mandatory. Excessive gain (clipping) disrupts the model's acoustic sensitivity. Resampling must use `audioop.ratecv` with persistent state to eliminate boundary noise.
- **Guaranteed Output Delivery**: Output frames must bypass the `mumble.is_ready()` check. Transmissions rely directly on the existence of the `sound_output` manager to ensure immediate playback.
- **Behavioral Mandate**: The `system_instruction` must include a hardcoded mandate for "verbal and immediate" responses to break potential silent "Listening" loops.
- **Bootstrap**: A text-based priming turn (`"Initial greeting"`) is required at session start to initialize the multimodal context.
