# Voice Detection Troubleshooting Guide

## Problem: Cellular Calls Not Detecting Speech

When calling through a cellular network → IVR → extension, the voice activity detection may fail due to:
- **Audio compression** by cellular carriers reduces volume
- **Noise suppression** by carrier/IVR removes dynamic range
- **Different codecs** (A-law vs μ-law) have different characteristics
- **Packet loss/jitter** from cellular network

## Solution: Adaptive Threshold Calibration

The bridge now automatically calibrates to different audio levels using these features:

### 1. Adaptive Threshold (Default)

**How it works:**
- Collects 3 seconds of baseline audio after welcome message
- Calculates noise floor (median) and peak background noise (75th percentile)
- Sets threshold dynamically based on: `noise_floor + (peak_noise - noise_floor) * 1.5`
- Range: 40 (minimum) to 300 (maximum)

**Expected behavior:**
```
Audio stats [CALIBRATING] - Current RMS: 72, Avg RMS: 68.5, Max RMS: 150, Threshold: 100
Audio stats [CALIBRATING] - Current RMS: 75, Avg RMS: 70.2, Max RMS: 150, Threshold: 100
Adaptive threshold calibrated: noise_floor=68, peak_noise=95, new_threshold=72
Audio stats [ACTIVE] - Current RMS: 115, Avg RMS: 85.3, Max RMS: 150, Threshold: 72
Started recording from caller (RMS: 115, threshold: 72)
```

### 2. Manual Override (For Testing)

If adaptive calibration isn't working, you can set a fixed threshold.

**Method 1: Environment Variable**
```bash
# Edit docker-compose.yml under sip-mumble-bridge service
environment:
  - VOICE_THRESHOLD=60        # Set fixed threshold (0 = adaptive)
  - SILENCE_THRESHOLD=2.0     # Seconds of silence to end utterance

# Restart service
docker-compose up -d sip-mumble-bridge
```

**Method 2: Direct Edit**
```bash
# Edit .env file
echo "VOICE_THRESHOLD=60" >> .env
echo "SILENCE_THRESHOLD=2.0" >> .env

# Restart service
docker-compose up -d sip-mumble-bridge
```

### 3. Enhanced Logging

The bridge now provides detailed diagnostics:

**Codec Information:**
```
Client offered codecs (payload types): 0 8 101
Received RTP packet 101, payload type: 0, payload size: 160 bytes
```
- Payload 0 = PCMU (μ-law)
- Payload 8 = PCMA (A-law)

**RMS Statistics (every 50 packets = 1 second):**
```
Audio stats [ACTIVE] - Current RMS: 115, Avg RMS: 85.3, Max RMS: 300, Threshold: 72
Recent RMS values: [68, 72, 115, 92, 88, 110, 95, 103, 87, 76]
```

## Troubleshooting Steps

### Step 1: Check Current Behavior
```bash
docker-compose logs -f sip-mumble-bridge | grep -E "(Audio stats|threshold|recording|Client offered)"
```

### Step 2: Analyze RMS Values During Speech

**Internal Call (Working):**
- RMS values: 200-2000 when speaking
- Avg RMS: 100-500
- Threshold works at: 100

**Cellular Call (Before Fix):**
- RMS values: 50-120 when speaking
- Avg RMS: 60-80
- Threshold fails at: 100 (too high)

### Step 3: Test Adaptive Calibration

1. **Rebuild with new changes:**
```bash
docker-compose build sip-mumble-bridge
docker-compose up -d sip-mumble-bridge
```

2. **Make a test call from cellular:**
```bash
# Watch logs during call
docker-compose logs -f sip-mumble-bridge
```

3. **Look for calibration message:**
```
Adaptive threshold calibrated: noise_floor=68, peak_noise=95, new_threshold=72
```

4. **Verify detection when speaking:**
```
Started recording from caller (RMS: 115, threshold: 72)
Silence detected, processing and transcribing audio (45 chunks)...
```

### Step 4: Manual Threshold Tuning (If Needed)

If adaptive calibration sets threshold too high or too low:

1. **Note your typical speaking RMS from logs:**
```
Recent RMS values: [65, 70, 110, 95, 88, 105, 92, 98, 85, 72]
```

2. **Set threshold to 60-70% of average speaking RMS:**
   - Speaking RMS: ~90 average, ~110 peaks
   - Set threshold to: 60 (90 × 0.67)

3. **Apply manual override:**
```bash
# Edit docker-compose.yml
environment:
  - VOICE_THRESHOLD=60

# Or use .env
echo "VOICE_THRESHOLD=60" >> .env

# Restart
docker-compose up -d sip-mumble-bridge
```

4. **Test and adjust:**
   - Too low (< 40): Picks up background noise
   - Too high (> 100): Misses speech on cellular
   - Sweet spot: 40-80 for cellular, 100-200 for internal

## Recommended Thresholds

| Call Type | Typical RMS | Recommended Threshold |
|-----------|-------------|----------------------|
| Internal SIP | 200-1000 | 100 (default) or adaptive |
| Cellular → IVR | 50-120 | 40-70 or adaptive |
| VoIP (compressed) | 80-200 | 60-100 or adaptive |
| Clean landline | 150-800 | 100 or adaptive |

## Additional Configuration

### Silence Threshold
How long to wait after speech stops before processing:
```bash
SILENCE_THRESHOLD=2.0  # Default: 2.0 seconds
```

- **Too short (< 1.5s):** Cuts off sentences mid-speech
- **Too long (> 3.0s):** Delays responses unnecessarily
- **Recommended:** 2.0-2.5s for natural speech

## Debugging Commands

### Real-time RMS monitoring:
```bash
docker-compose logs -f sip-mumble-bridge | grep "Audio stats"
```

### Check calibration events:
```bash
docker-compose logs sip-mumble-bridge | grep -E "(calibrated|threshold)"
```

### Monitor recording events:
```bash
docker-compose logs -f sip-mumble-bridge | grep -E "(Started recording|Silence detected|Transcribed)"
```

### Check codec negotiation:
```bash
docker-compose logs sip-mumble-bridge | grep -E "(Client offered|payload type)"
```

## Expected Results After Fix

**Successful Cellular Call:**
```
[11:46:10] Using adaptive voice threshold calibration
[11:46:12] Audio stats [CALIBRATING] - Current RMS: 68, Avg: 66.2, Threshold: 100
[11:46:13] Audio stats [CALIBRATING] - Current RMS: 72, Avg: 68.5, Threshold: 100
[11:46:14] Adaptive threshold calibrated: noise_floor=65, peak_noise=88, new_threshold=69
[11:46:15] Audio stats [ACTIVE] - Current RMS: 72, Avg: 70.1, Threshold: 69
[11:46:16] Started recording from caller (RMS: 112, threshold: 69)
[11:46:17] Audio stats [ACTIVE] - Current RMS: 105, Avg: 92.3, Threshold: 69
[11:46:18] Silence detected, processing and transcribing audio (92 chunks)...
[11:46:19] Processing 1.84 seconds of audio
[11:46:21] Transcribed: Hello, can you hear me?
```

## Still Not Working?

If speech detection still fails after these changes:

1. **Share full logs** from call start to end:
```bash
docker-compose logs sip-mumble-bridge > sip-debug.log
```

2. **Include these key sections:**
   - Codec negotiation (SDP parsing)
   - Calibration message
   - Multiple "Audio stats" lines during active speech
   - Any "Started recording" or timeout messages

3. **Test with manual threshold:**
   - Start with `VOICE_THRESHOLD=40`
   - If that works, gradually increase until you find optimal value
   - Report working threshold for your setup

## Common Issues

**Issue: Threshold calibrates too high**
- Cause: Bot audio contaminating baseline
- Fix: Welcome message mutes/unmutes properly, but try `VOICE_THRESHOLD=50` manually

**Issue: Constant recording (background noise)**
- Cause: Threshold too low
- Fix: Increase `VOICE_THRESHOLD` or disable adaptive with `VOICE_THRESHOLD=100`

**Issue: Cuts off sentences mid-word**
- Cause: Silence threshold too short
- Fix: Increase `SILENCE_THRESHOLD=2.5` or `3.0`

**Issue: Long delay before response**
- Cause: Silence threshold too long
- Fix: Decrease `SILENCE_THRESHOLD=1.5` or `1.8`

