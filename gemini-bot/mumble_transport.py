import asyncio
import os
import pymumble_py3
import pymumble_py3.constants
import audioop
from loguru import logger

class MumbleInputTransport:
    def __init__(self, mumble=None):
        self._mumble = mumble
        self._loop = None
        self._input_ready = False
        self._audio_queue = asyncio.Queue()
        self._producer_task = None
        self._myself_session = None
        self._resample_state = None 

    def set_mumble(self, mumble, loop):
        self._mumble = mumble
        self._loop = loop

    async def start(self):
        logger.debug("MumbleInput: Initializing transport")
        self._loop = asyncio.get_running_loop()
        self._input_ready = True
        
        if self._mumble and self._mumble.users.myself:
            self._myself_session = self._mumble.users.myself['session']
            logger.info(f"MumbleInput: Identified self session ID {self._myself_session} for filtering")

    async def stop(self):
        self._input_ready = False

    def _on_sound_received(self, user, sound):
        # 1. Filter out self-audio
        if self._myself_session is not None and user['session'] == self._myself_session:
            return

        if not self._input_ready or not self._loop:
            return

        try:
            # 2. Extract RAW PCM from Mumble (48kHz mono)
            raw_audio = sound.pcm
            
            # 3. Resample to 16kHz (width=2, channels=1) for Gemini
            audio_16k, self._resample_state = audioop.ratecv(
                raw_audio, 2, 1, 48000, 16000, self._resample_state
            )
            
            # 4. Push to the internal queue WITHOUT blocking the Mumble thread
            self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, audio_16k)

        except Exception as e:
            logger.error(f"MumbleInput Callback Error: {e}")

    async def get_audio_frame(self):
        """Standard interface for the SDK loop to pull audio."""
        return await self._audio_queue.get()


class MumbleOutputTransport:
    def __init__(self, mumble=None):
        self._mumble = mumble
        self._resample_state = None 

    def set_mumble(self, mumble):
        self._mumble = mumble

    async def write_audio(self, data: bytes, sample_rate: int = 24000):
        """Directly resamples and pushes to Mumble sound_output sink."""
        try:
            # 1. SPEC: Use Unity Gain (1.0x) to eliminate clipping
            boosted_audio = audioop.mul(data, 2, 1.0)

            # 2. Resample from Gemini (usually 24k) to 48k for Mumble
            audio_48k, self._resample_state = audioop.ratecv(
                boosted_audio, 2, 1, sample_rate, 48000, self._resample_state
            )
            
            # 3. SDK Bypass: Guaranteed delivery path.
            if self._mumble and hasattr(self._mumble, "sound_output") and self._mumble.sound_output:
                self._mumble.sound_output.add_sound(audio_48k)
            else:
                logger.warning("MumbleOutput: DROPPED bytes because SoundOutput is not available")
        except Exception as e:
            logger.error(f"MumbleOutput ERROR in write_audio: {e}")


class MumbleTransport:
    def __init__(self, mumble):
        self._mumble = mumble
        self._input = MumbleInputTransport(mumble)
        self._output = MumbleOutputTransport(mumble)
        
        # Set callback for audio input. 
        self._mumble.callbacks.set_callback(
            pymumble_py3.constants.PYMUMBLE_CLBK_SOUNDRECEIVED,
            self._input._on_sound_received
        )

    def input(self):
        return self._input

    def output(self):
        return self._output
