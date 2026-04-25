# Custom Mumble Bots Specification

This document outlines the technical specifications and requirements for the custom bots managed in the FTPodcastMurmurHost ecosystem. You must take this document literally when implementing. If there are any contradictions or ambiguities, STOP and ask for clarification.


## Bot Presence
- All presence (and mute status) logic should be Event-driven
    - Do NOT create constant polling loops to check status unless events are confirmed to be unavailable
- Running status of a bot's container should be coupled to presence in server
- **Supervisor Presence**:
    - Room: Root
        - When moved, return to Root immediately
    - Joins when server starts
    - Never leaves
    - When kicked from server:
        - Restarts own container (which triggers restart of other bots)
- **Echo Bot Presence**:
    - Joins when:
        - mic-unverified humans are present anywhere on the server 
        - OR someone is in "Mic Check"
    - Channel: Mic Check only
    - Leaves when:
        - the Mic Check channel is empty
        - AND there are no mic-unverified humans on the server
    - When kicked from server:
        - Rejoin based on same rules
- **Recording Bot Presence**:
    - Joins server when:
        - Stage is occupied by any human
    - Channel: Audience only
    - Leaves server when:
        - Stage is empty for 30 seconds
    - When kicked from server:
        - Stay offline until a positive change in Stage occupancy occurs (i.e., a person joins)
    - Container:
        - Must exit and shut down gracefully - e.g. recordings in progress save properly
- **Live AI Bot Presence**:
    - Joins server when:
        - Studio channels OR Hallway channels are occupied by any human
        - AND AI Service is available
    - Initial Channel:
        - `AI Test Room`, if it exists (temp channel and simulated humans can be created for testing)
        - otherwise `Audience`
        - May be moved by users, or by agent's own tools
        - Shall never join a channel with Echo Bot
    - Leaves server when:
        - Studio/Hallway subchannels are empty for 30 seconds
        - OR AI service is unavailable
    - When kicked from server:
        - Stay offline until a positive change in Studio occupancy occurs (i.e., a person joins)
- **Testing Bot Presence**:
    - Channel: Decided by testing Agent
    - Multiple Testing bots may be spawned as needed - use different names
    - Always offline/disabled by default
    - Runs when triggered manually by Agent for testing of other bots
    - Agent should shut down Testing bot after testing is complete


## Mic Verification System:
A human is mic-verified when:
    - they have been present in the Mic Check channel for 3 seconds
    - AND they were detected to be speaking at least once in that channel
Verification status persists for 60 seconds after a user leaves the server.


## 🛡️ Supervisor Bot (`supervisor_bot.py`)
Central orchestrator for all bot activity and presence management.

- Name: always "Supervisor"
- Always connected, in the Root channel, deafened, and muted.
- Manages other bots as docker containers.
- Periodically updates its own **User Comment** with a detailed report of all bots' status and verification counts.

---

## 🎥 Recording Bot (`opus_recorder.py`)
High-fidelity session recorder that captures individual user streams. Sits in the Audience channel (which can hear the Stage) when humans are in the Stage channel.

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

## 🤖 Gemini Live AI Bot (`gemini-bot/bot.py`)
AI interaction bot powered by Gemini Live API.

- **Name**: Always "Benny Botman"
- **Core Model**: `gemini-3.1-flash-live-preview`.
- **Voice**: `Fenrir`
- **API Configuration**:
    - Must use `v1beta`
    - Audio must be downsampled to 16k
    - Audio Transcripts:
        - `output_audio_transcription`: Enabled.
        - `input_audio_transcription`: Enabled.
        - Agent should refer to logs when testing to confirm conversation responses.
- **Agent Tools**:
    - Change channel tool:
        - Always available
        - Enumerates valid channel moves based on client permissions
        - Leaving a channel only occurs before or after agent finishes speaking, never during
            - Thus synchronous - default blocking behavior
    - Channel Message tool:
        - Always available
        - Enumerates valid channels to message based on client permissions
        - Called asynchronously (i.e. can use tool during human's turn)
            - Use `"behavior": "NON_BLOCKING"`
    - Direct Message tool:
        - Always available
        - Enumerates valid users to message based on client permissions
        - Called asynchronously (i.e. can use tool during human's turn)
            - Use `"behavior": "NON_BLOCKING"`
    - Grounding with Google Search
    - Note: Non-tool text output is sent as a message to the Studio channel (seen in all child channels).
- **Bot Behavior**:
    - Self-Mute Status:
        - Bot is ALWAYS muted when the Live API is not connected.
        - Bot is ALWAYS unmuted when the Live API is connected and streaming what it hears.
        - Bot's self-mute status should be a reliable indicator of API connection, even dropouts that are smoothed over.
    - Self-Deafened Status:
        - Bot is ALWAYS deafened when it is not buffering audio nor streaming to the Live API.
        - Bot is ALWAYS undeafened when streaming to the API, OR buffering audio to be sent upon connect.
        - Bot's self-deafened status should be a reliable indicator of whether the bot is "listening", even if not yet connected.
    - Streaming Connection is ALLOWED only:
        - Whenever in a channel with permission to speak
            - NOT force-muted or force-deafened (suppressed) channels
    - Streaming Connection should start: 
        - when speaking is allowed 
        - AND any human that can be heard from this channel has started transmitting
            - Stay disconnected until first human speech starts, mute status reflects this
            - Audio should be buffered from the start even if API does not connect immediately
    - While streaming:
        - Live API's built-in VAD should still be used - just because a mumble client is transmitting, does not mean it's valid speech - let API-side VAD handle this
    - Streaming should be ended by bot when:
        - Bot is muted by another user: Session ends, bot moves to Audience (if on Stage)
        - No one has spoken for 60 seconds
    - When streaming ends while on stage:
        - Bot should move to Audience channel
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
