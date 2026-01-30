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

**Recommendation**: You **MUST** use the 200ms silence packet structure. Do not reduce size or change to text.
