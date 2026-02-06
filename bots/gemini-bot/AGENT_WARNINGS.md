# Agent Warnings

This document tracks implementation details that were found to be critical for the Gemini Bot's stability. **Do not deviate from these patterns.**

## 1. Sender Loop & Keep-Alives
**Status**: CRITICAL
**Description**: The `sender_loop` **MUST** include a mechanism to send keep-alive silence packets when the queue is empty.
**Failure Mode**: Removing the keep-alive logic (or the `asyncio.wait_for` timeout that triggers it) results in **TOTAL SILENCE** from the bot. The connection appears open, but no responses are received.
**Working Pattern**:
```python
try:
    # 4.0s timeout is critical
    item = await asyncio.wait_for(self.to_gemini_queue.get(), timeout=4.0)
except asyncio.TimeoutError:
    # Send silence if not speaking
    # ...
```

## 2. Configuration Object vs Dict
**Status**: INFO
**Description**: The bot functions correctly with both dictionary-based config and `types.LiveConnectConfig` object.
**Recommendation**: Use `types.LiveConnectConfig` to adhere to `CUSTOM_BOTS_SPEC.md`.

## 3. Resumption & Tools
**Status**: INFO
**Description**: Disabling `SlidingWindow` or `tools` in the configuration **does not** fix the missing resumption token issue.
**Observation**: The server consistently sends `new_handle=None` regardless of these settings for the `gemini-2.5-flash-native-audio-preview-12-2025` model.


## 4. Keep-Alive Payloads
**Status**: WARNING

## 4. Keep-Alive Payloads

## 4. Keep-Alive Payloads (CRITICAL)
**Status**: CRITICAL
**Description**: The Gemini 2.5 model is extremely sensitive to the keep-alive silence payload.
**Findings**:
- **200ms Silence (`b'\x00' * 3200`)**: **SUCCESS** for Turn 1. Bot speaks. (May cause `1008` error later if session idles).
- **10ms Silence (`b'\x00' * 320`)**: **FAILURE**. Turn 1 is silent. Bot ignores input.
- **text=" " Keep-Alive**: **FAILURE**. Turn 1 is silent.
- **No Keep-Alive**: **FAILURE**. Turn 1 is silent.

**Recommendation**: You **MUST** use the 200ms silence packet structure (`b'\x00' * 6400` or similar). Do not reduce size or change to text.

## 5. Comfort Noise & VAD Helper Regressions
**Status**: WARNING
**Description**: Attempts to "help" Gemini by interleaving silence (Comfort Noise) or appending silence (VAD Helper) failed.
**Failure Mode**: Gemini becomes "confused" by the artificial silence gaps or the abrupt injection of large silence blocks, leading to Turn 1 failures or total silence.
**Rule**: Send only **REAL** audio from the user, or a single heartbeat silence when completely idle for > 4s. Never interleave.

## 6. Server Response Errors (Dashboard Monitoring)
**Status**: CRITICAL
**Description**: The following errors have been observed in the Google AI Dashboard. **Do not suppress these in the code.** They MUST be logged clearly.
- **400 Bad Request**: Often due to malformed tool responses or config.
- **404 Not Found**: Model ID or Resource issues.
- **409 Conflict**: Overlapping session attempts (ensure `connecting_lock` usage).
- **500 Internal Server Error**: Gemini-side failure (requires backoff/re-connection).
- **501 Not Implemented**: feature/config mismatch.
- **503 Service Unavailable**: Temporary unavailability (requires retry).

## 7. Proactive Idle Reset
**Status**: RECOMMENDED
**Description**: To prevent `1008` (Policy Violation) and `1011` (Internal Error) on multi-turn conversations, the bot should proactively reset the session after 5 seconds of idle between turns.
**Rationale**: Re-establishing a fresh connection ensures a clean slate for recognition and reduces the chance of server-side state corruption.
