# Custom Mumble Bots Specification

This document outlines the technical specifications and requirements for the custom bots managed in the FTPodcastMurmurHost ecosystem.


## Bot Presence
- **Supervisor Presence**:
    - Room: Root
        - When moved, return to Root immediately
    - Joins when server starts and is fully warmed up
    - Never leaves
    - When kicked from server:
        - Rejoin immediately
- **Echo Bot Presence**:
    - Room: Mic Check only
    - Joins when:
        - mic-unverified humans are present anywhere on the server 
        - OR someone is in "Mic Check"
    - Leaves when:
        - the Mic Check room is empty
        - AND there are no mic-unverified humans on the server
    - When kicked from server:
        - Rejoin based on same rules
- **Recording Bot Presence**:
    - Room: Audience only
    - Joins when:
        - Stage is occupied by any human
    - Leaves when:
        - Stage is empty for 60 seconds
    - When kicked from server:
        - Stay offline until a positive change in Stage occupancy occurs (i.e., a person joins)
- **PodBot Presence**:
    - Room: Audience (initially)
    - Joins when:
        - Studio (or subrooms) are occupied by any human
        - AND AI Service is available
    - Leaves when:
        - Studio (or subrooms) are empty for 30 seconds
        - OR AI service is unavailable
    - When kicked from server:
        - Stay offline until a positive change in Studio occupancy occurs (i.e., a person joins)
- **Testing Bot Presence**:
    - Room: Decided by testing Agent
    - Multiple Testing bots may be spawned as needed - use different names
    - Always offline/disabled by default
    - Runs when triggered manually by Agent for testing of other bots
    - Agent should shut down Testing bot after testing is complete


## Mic Verification System:
A human is mic-verified when:
    - they have been present in the Mic Check room for 3 seconds
    - AND they were detected to be speaking at least once in that room
Verification status persists for 60 seconds after a user leaves the server.


## 🛡️ Supervisor Bot (`supervisor_bot.py`)
Central orchestrator for all bot activity and presence management.

- Name: always "Supervisor"
- Always connected, in the Root channel, deafened, and muted.
- Manages other bots as subprocesses.
- Implements a 20-second cooldown between start attempts of the same bot to prevent "Username already in use" errors.
- Periodically updates its own **User Comment** with a detailed report of all bots' status and verification counts.

---

## 🎥 Recording Bot (`opus_recorder.py`)
High-fidelity session recorder that captures individual user streams.

- **Bot Naming Scheme**: `Recording (Session YYYY-MM-DD)`.
    - Sessions starting before 07:00 AM are attributed to the previous calendar day.
- **Technical Features**:
    - Bit-perfect Opus muxing that records the raw audio from each user in the exact bitrate it was received without re-encoding.
    - Generates **WebVTT** files for speaker-labeled transcripts.
    - Silence packet injection:
        - Synchronizes audio across users using session start-time offsets
        - Prevents audio from having silences skipped when opened in e.g. Audacity
- **File Organization**:
    - Target Folder: `recordings/Session YYYY-MM-DD`
- **Lifecycle**: Started/Stopped by the Supervisor based on presence rules. Leaves server if crash occurs.

---

## 🤖 Gemini Live Bot (`gemini-bot/bot.py`)
AI interaction bot powered by Gemini Live API.

- **Name**: Always "Benny Botman"
- **Core Model**: `gemini-2.5-flash-native-audio-preview-12-2025`.
- **Voice**: `Fenrir`
- **API Configuration**:
    - Audio Transcripts:
        - `output_audio_transcription`: Enabled.
        - `input_audio_transcription`: Enabled.
        - Agent should refer to logs when testing to confirm conversation responses.
    - `enable_affective_dialog`: Enabled for natural speech patterns.
    - `proactive_audio`: Allow the model to decide not to respond. Important for when humans are talking to each other rather than to the bot.
- **Agent Tools**:
    - Self-mute tool:
        - Available when not muted.
        - Called synchronously (blocking; i.e. mute occurs after agent finishes speaking)
            - Necessary since  Modality will change
    - Self-unmute tool:
        - Available when muted AND in a room with permission to unmute.
        - Called asynchronously (i.e. can use tool during human's turn)
            - Use `"behavior": "NON_BLOCKING"`
            - Use `scheduling="SILENT"`
    - Change room/channel tool:
        - Always available
        - Enumerates valid channel moves based on client permissions
        - Leaving a room only occurs before or after agent finishes speaking, never during
    - Room Message tool:
        - Always available
        - Enumerates valid channels to message based on client permissions
        - Called asynchronously (i.e. can use tool during human's turn)
    - Direct Message tool:
        - Always available
        - Enumerates valid users to message based on client permissions
        - Called asynchronously (i.e. can use tool during human's turn)
    - Grounding with Google Search
- **Modality Logic**:
    - Live API **AUDIO** Mode:
        - Whenever in a room with permission to speak -- NOT force-muted or force-deafened (suppressed) rooms -- AND any human that can be heard from this room has started transmitting.
        - When muted:
            - VAD disabled -- audio is sent continuously as one "user's turn" of the conversation in the API.
            - Live Agent may still decide to use unmute tool at any time, so we can ask it to unmute itself rather than doing it in the UI.
        - When unmuted:
            - VAD resumed -- Live API decides when "user's turn" ends and when to speak.
            - Agent may use tool to mute itself.
            - Bot should self-mute when agent sends empty reply (proactive audio feature).
        - When deafened:
            - Leave gap in stream - audio should resume when undeafened as if gap never occured
    - Live API **TEXT** Mode:
        - Whenever in a room WITHOUT permission to speak AND not suppressed.
        - If in Studio/subrooms, non-tool text output is sent as a message to the Studio room/subrooms.
        - Live Agent may still use tools to send direct messages, send messages to specific channels, etcetera. (Live Agent is encouraged to use message tools rather than output text.)
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
            - Bot self-muted if not already
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
    - Connection dropped during TEXT streaming:
        - Use exponential backoff retry strategy.
        - Provide all context from previous session to new session.
    - Contxt window exceeded:
        - Truncate first 50% of history.
        - Log warning to server chat.
- **Usage Tracking**: Displays real-time stats in its Mumble User Comment.
    - Token usage:
        - tracked by in the usageMetadata field of the returned server message
        - shown as a fraction out of the API Quota: ` 0 / 128,000`
    - Request count:
        - tracked by counting the number of turns that have occured since midnight.
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

- **Function**: Bounces all incoming audio back to the speaker with minimal latency.
- **Purpose**: Used by users to verify their audio settings and by the Supervisor to confirm human audio activity.
- **Lifecycle**: Purely managed by the Supervisor; only joins when humans need verification.

---

## 🧪 Testing Bot (`test_bot.py`)
Automated verification tool to simulate user behavior.

- **Manual Tool**: This bot is **not** managed by the Supervisor. It must be manually launched on demand by the coding agent for verification purposes.
- **Mock Human**: Joins channels, moves between rooms, and plays back audio samples to test other bots.
- **Audio Simulation**: Uses `ffmpeg` to pipe existing `.opus` recordings into the server as natural speech.
- **Usage**: Primary tool for validating Supervisor presence logic and Mic Check verification in CI/CD or local development.

# Addendum: Room name mapping and heirarchy
Unless explicitly specified, bot logic should rely on user permissions in a channel rather than the channel name - channel names and permissions may change.

- Root: "Podcast Server"
    - Mic Check: "Mic Check 🎧"
    - Studio: "Studio 🗣️"
        - Audience: "Audience 👂"
        - Backstage: "Backstage 🤐"
        - Stage: "🎙️ Stage 🔴"
    - Hallway: Hallway 🖉
        - Used to contain temporary rooms - any user can create temporary rooms