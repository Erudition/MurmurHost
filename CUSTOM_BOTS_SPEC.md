# Erudition Murmur Custom Bots Specification

This document defines the requirements, constraints, and architecture for the custom bots managed within this repository.

## 🛡️ Supervisor Bot (`supervisor_bot.py`)
Central orchestrator for all bot activity and presence management.

- Name: always "Supervisor"
- Always connected, in the Root channel, deafened, and muted.
- Manages other bots as docker containers.
- Periodically updates its own **User Comment** with a detailed report of all bots' status and verification counts.
- **Protobuf Conflict**: Due to `pymumble` requiring Protobuf 3.x and Pipecat requiring 4.x/5.x, set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` in the environment.
- **Pymumble Installation**: Install `pymumble` from git (`https://github.com/azlux/pymumble.git`) using `--no-deps` to bypass metadata-level version conflicts.
- **Dependencies**: Manually ensure `opuslib` and `libopus-dev` are installed as they are required by `pymumble` but may be skipped during `--no-deps` install.
- **Service Type**: Use `GeminiLiveLLMService` for native multimodal support.

## 🤖 Gemini Live Bot (`pipecat_bot.py`)
Advanced multimodal conversational AI powered by Google's Gemini Live API.

- **Objective**: Provide high-fidelity, bidirectional conversational AI on the Mumble server.
- **Framework**: Built on `pipecat-ai` with `google-genai` integration.
- **Uplink Standard**: Uses the `v1beta` Live API for low-latency interactive reachability.
- **Audio Sensitivity**: Implements Unity Gain (1.0x) and phase-locked resampling (16kHz in / 48kHz out) to ensure the model's acoustic encoder receives a pristine signal.
- **State Mastery**: Uses an explicit `audio_stream_end=True` turn-switch signal during a 500ms silence flush to force the model from "Listening" to "Generating" state.
- **Delivery Path**: Bypasses transient Mumble sync-state checks (`is_ready()`) for guaranteed real-time playback.
- **Interaction Model**: Standardized on a "Reactive + Primed" initialization flow with a hardcoded Interactive Mandate in the system instruction.
- **Failure Handling**:
    - Session duration exceeded:
        - details at https://ai.google.dev/gemini-api/docs/live-session
        - connection lifetime is limited to around 10 minutes
        - Audio sessions are limited by the API (15 minutes if compression is not used)
            - Use context window compression and session resumption features
                - set `contextWindowCompression` config to use `types.SlidingWindow()` 
            - configure the sessionResumption field to smoothly handle WebSocket resets
                - Use SessionResumptionUpdate messages to resume the session by passing the last resumption token (valid for 2hrs) as the SessionResumptionConfig.handle of the subsequent connection.
    - GoAway Message Recieved
        - Log the `timeLeft` to server chat
    - Quota Exceeded: 
        - Log error to server chat.
        - Rotate to another API key if available.
            - Maintain context in new session if successful.
        - If all API keys fail:
            - Log error to server chat
            - Bot goes offline
            - Normal presence logic resumes when (the time that the Gemini Live API considers midnight) passes.
    - Connection dropped during AUDIO streaming:
        - Auto reconnection period:
            - Bot self-mutes
            - Log error to server chat
            - Bot continues to buffer audio
            - Retry with backoff strategy:
                - 2 seconds
                - 5 seconds
                - 10 seconds
            - Upon reconnection, flush audio buffer for seamless conversation
        - After failure to reconnect:
            - Bot goes offline
            - Normal presence logic resumes after 10 minutes.
- **Usage Tracking**: Displays real-time stats in its Mumble User Comment, updated after every turn.
    - Token usage:
        - tracked by in the usageMetadata field of the returned server message
        - shown as a fraction out of the Context Window Size: ` 0 / 128,000`
    - Request count:
        - tracked by counting the number of turns that have occured since midnight.
            - This must therefore be remembered even when the bot leaves and comes back.
        - shown as a fraction out of the API Quota: ` 0 / 50 ` (Preview Model Limit)
    - Show separate stats for each API Key.
    - Dropouts (since joining the server)
        - Show total number of disconnection incidents.
        - Show average number of retries until success.
        - Show total number of eventually-successful retries as fraction out of total number of retry periods.
        - Show total duration of disconnection incidents.

---

## 🔄 Echo Bot (`echobot.py`)
Minimal audio verification utility.

- **Function**: Transitions between two modes based on user verification status:
    - **Echo Mode (Unverified)**: Bounces all incoming audio back to the speaker with minimal latency.
    - **Parrot Mode (Verified)**: 
        - Buffers incoming audio while the human is speaking (VAD active).
        - Plays back the entire buffer only after the human stops speaking.
        - **Interruption Logic**: If the human starts speaking again during the bot's playback, the bot must immediately stop its playback, clear its outgoing audio queue, and discard the interrupted buffer.
    - Sends "Mic Checked - I can hear you! Switching to Parrot Mode." to the user when they have been sucessfully echoed AND present in the Mic Check channel for more than 3 seconds.
        - Only sent once, even if user stays in channel.
- **Purpose**: Used by users to verify their audio settings and by the Supervisor to confirm human audio activity.
- **Lifecycle**: Purely managed by the Supervisor; only joins when humans need verification.

---

## 🧪 Simulated Humans (`test_bot.py`)
Automated verification tool to simulate user behavior.

- **Manual Tool**: This bot is **not** managed by the Supervisor. It must be manually launched on demand by the coding agent for verification purposes.
- **Mock Human**: Joins channels, moves between channels, and plays back audio samples to test other bots.
- **Audio Simulation**: Uses `ffmpeg` to pipe existing `.opus` recordings from `test-speech-clips` into the server as natural speech.
    - The recording filenames match the content, so their use cases should be obvious.
    - Remember to unmute before playback. All users that join the server are initially muted, and when leaving a force-muted channel, one must still unmute themselves in the new channel.
    - Test AI with at least two audio clips (one after the response) to confirm follow-up ability. Don't claim success until you can see the transcription of the second response.
- **Channel Creation**: Creates temporary channels in the Hallway whenever test environments are needed. 
    - Clients must connect with a certificate to take advantage of this permission.
    - Warning: Due to echo bot's feedback loop, Mic Check channel should only be used for testing related functionality.
    - To prevent junk recordings, only use the stage when testing the recorder.
- **Usage**: Primary tool for validating Supervisor presence logic and Mic Check verification, and Gemini API reactions, by the coding agent.

# Certificates
- Clients must join with certificates to be Registered.
- Special permissions granted to users will not be available if not registered, even if the username matches.
- Registration means anyone that then joins by that username will be rejected if they do not have the correct certificate.
- Therefore, bots needing special permissions (e.g. Supervisor) must have persistent certificates, be manually registered in the UI, and then manually assigned ACL roles in the UI.
- Store certs in `certs`.

# Addendum: Channel name mapping and heirarchy
Unless explicitly specified, bot logic should rely on user permissions in a channel rather than the channel name - channel names and permissions may change.

- Root: "Podcast Server" (Supervisor only)
    - Mic Check: "Mic Check 🎧" (Humans and Echo Bot only - 2-user capacity limit)
    - Studio: "Studio 🗣️"
        - Parent only - Cannot be directly occupied. All children can hear stage.
        - Audience: "Audience 👂"
        - Backstage: "Backstage 🤐"
        - Stage: "🎙️ Stage 🔴"
    - Hallway: Hallway 🖉
        - Parent only - Cannot be directly occupied
        - Used to contain temporary channels - any user can create temporary channels

# Test Procedures

These procedures define the standard verification suite for Benny Bot stability and feature compliance.

## 🟢 Multi-Turn Baseline Test (`multi_turn_test.py`)
This test verifies the stability of the Gemini Live API connection, VAD responsiveness, and context retention across multiple interactions.

- **Environment**: AI Test Room (Temporary channel in Hallway).
- **Participants**: 
    - `BennyBot`: The bot under test (launched via the script using `v1beta` API).
    - `TestDriver`: A simulated human that plays audio clips.
- **Workflow**:
    - **Turn 1**: The Driver plays `hey-benny-can-you-hear-me.opus`.
    - **Turn 2**: The Driver plays `hey-benny-name-all-the-channels.opus`.
    - **Turn 3**: The Driver plays `create-a-channel-then-move-to-it.opus`.
    - **Event-Driven Execution**:
        - **Detection**: The test suite monitors `BennyBot`'s transmission status in Mumble for each turn.
        - **Response**: The test suite MUST see audio being transmitted from `BennyBot`'s client. 
            - **Timeout**: If no audio is transmitted within 30 seconds of the trigger, the test fails immediately.
        - **Turn Progression**: The next clip in the sequence is played IMMEDIATELY after `BennyBot` stops transmitting. No fixed timers or sleeps are used between turns.
- **Success Criteria**:
    - "Turn Complete" signal received from Gemini for all 3 turns.
    - Successful audio transmission detected in Mumble for every turn.
    - No WebSocket disconnections (1008 or 1007 errors).
    - Clear transcription log of model responses.
