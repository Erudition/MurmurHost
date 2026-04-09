
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
