import asyncio
import audioop
import logging
from typing import Optional

from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, StartFrame, Frame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams

logger = logging.getLogger("MumbleTransport")

class MumbleInputTransport(BaseInputTransport):
    def __init__(self, mumble_client, params: TransportParams):
        super().__init__(params)
        self._mumble = mumble_client
        self._loop = asyncio.get_running_loop()
        self._audio_in_queue = asyncio.Queue()
        # Hook into Mumble callback
        self._mumble.callbacks.set_callback("sound_received", self._on_sound_received)

    async def start(self, frame: StartFrame):
        await super().start(frame)
        await self.set_transport_ready(frame)

    def _on_sound_received(self, user, sound):
        # Callback from Pymumble thread. sound.pcm is 48000Hz, 1ch, 16bit.
        # We need to push this to the Pipecat loop.
        asyncio.run_coroutine_threadsafe(
            self._async_push_audio(sound.pcm), 
            self._loop
        )

    async def _async_push_audio(self, pcm_data):
        if self._params.audio_in_enabled:
            try:
                # Resample 48000 -> 16000 for Pipecat/VAD
                resampled_audio, _ = audioop.ratecv(pcm_data, 2, 1, 48000, 16000, None)
                
                # Check volume (RMS)
                rms = audioop.rms(resampled_audio, 2)
                if rms > 100: # Only log if there's some sound
                    logger.debug(f"Pushed audio frame: len={len(resampled_audio)}, rms={rms}")
                
                frame = InputAudioRawFrame(audio=resampled_audio, sample_rate=16000, num_channels=1)
                await self.push_audio_frame(frame)
            except Exception as e:
                logger.error(f"Error pushing audio: {e}")

class MumbleOutputTransport(BaseOutputTransport):
    def __init__(self, mumble_client, params: TransportParams):
        super().__init__(params)
        self._mumble = mumble_client

    async def write_audio_frame(self, frame: OutputAudioRawFrame):
        # Bot Speech (Pipecat -> Mumble)
        if self._params.audio_out_enabled:
            audio = frame.audio
            # Gemini Live often sends 24000Hz. Mumble expects 48000Hz.
            if frame.sample_rate != 48000:
                try:
                    audio, _ = audioop.ratecv(audio, 2, 1, frame.sample_rate, 48000, None)
                except Exception as e:
                    logger.error(f"Error resampling for output: {e}")
            
            # Push back to Mumble
            rms = audioop.rms(audio, 2)
            logger.info(f"MumbleOutputTransport: Sending audio to Mumble, len={len(audio)}, rms={rms}")
            self._mumble.sound_output.add_sound(audio)

class MumbleTransport(BaseTransport):
    def __init__(self, mumble_client, params: TransportParams):
        super().__init__()
        self._mumble = mumble_client
        self._params = params
        self._input: Optional[MumbleInputTransport] = None
        self._output: Optional[MumbleOutputTransport] = None

    def input(self) -> FrameProcessor:
        if not self._input:
            self._input = MumbleInputTransport(self._mumble, self._params)
        return self._input

    def output(self) -> FrameProcessor:
        if not self._output:
            self._output = MumbleOutputTransport(self._mumble, self._params)
        return self._output
