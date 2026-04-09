import asyncio
import audioop
import logging
from typing import Optional

from pipecat.frames.frames import (
    Frame, 
    StartFrame, 
    EndFrame, 
    InputAudioRawFrame, 
    OutputAudioRawFrame, 
    OutputTransportReadyFrame,
    SystemFrame
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams



logger = logging.getLogger("MumbleTransport")

class MumbleInputTransport(BaseInputTransport):
    def __init__(self, mumble_client, params: TransportParams):
        super().__init__(params)
        self._mumble = mumble_client
        self._loop = asyncio.get_running_loop()
        self._input_ready = False
        # Hook into Mumble callback
        self._mumble.callbacks.set_callback("sound_received", self._on_sound_received)

    async def start(self, frame: StartFrame):
        await super().start(frame) # BaseInputTransport.start
        # Ensure the started flag is set to allow following frames to pass _check_started
        self._StartFrame_processed = True
        logger.info(f"MumbleInput({id(self)}) started. Flag set: {self._StartFrame_processed}")
        # DO NOT push StartFrame here; PipelineTask handles it.
        # Manual pushing causes double-initialization of downstream services.
        self._input_ready = True

    def _on_sound_received(self, user, sound):
        self._loop.call_soon_threadsafe(self._sync_process_audio, sound.pcm)

    def _sync_process_audio(self, pcm_data):
        if not self._input_ready:
             return

        try:
            # Resample from 48000 (Mumble) to 16000 (Pipecat)
            resampled_audio, _ = audioop.ratecv(pcm_data, 2, 1, 48000, 16000, None)
            # Gain boost
            resampled_audio = audioop.mul(resampled_audio, 2, 10.0)
            rms = audioop.rms(resampled_audio, 2)
            
            # logger.debug(f"MumbleInput({id(self)}): rms={rms}, ready={self._input_ready}")
            
            if rms > 100:
                # logger.debug(f"MumbleInput({id(self)}): pushing frame, rms={rms}")
                frame = InputAudioRawFrame(audio=resampled_audio, sample_rate=16000, num_channels=1)
                asyncio.run_coroutine_threadsafe(self.push_frame(frame), self._loop)
        except Exception as e:
            logger.error(f"MumbleInput audio error: {e}")

class MumbleOutputTransport(BaseOutputTransport):
    def __init__(self, mumble_client, params: TransportParams):
        super().__init__(params)
        self._mumble = mumble_client

    async def start(self, frame: StartFrame):
        # Initialize internal variables but skip media senders
        self._sample_rate = self._params.audio_out_sample_rate or frame.audio_out_sample_rate
        logger.debug(f"MumbleOutputTransport started with sample_rate={self._sample_rate}")
        await self.push_frame(OutputTransportReadyFrame(), FrameDirection.UPSTREAM)

    async def stop(self, frame: EndFrame):
        logger.debug("MumbleOutputTransport stopped")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Direct handling for audio to skip BaseOutputTransport's media sender logic
        if isinstance(frame, OutputAudioRawFrame):
            if self._params.audio_out_enabled:
                audio_data = frame.audio
                if frame.sample_rate != 48000:
                    try:
                        audio_data, _ = audioop.ratecv(audio_data, 2, 1, frame.sample_rate, 48000, None)
                    except Exception as e:
                        logger.error(f"Error resampling for output: {e}")
                        return
                self._mumble.sound_output.add_sound(audio_data)
                logger.debug(f"MumbleOutput: added {len(audio_data)} bytes of audio to buffer")
        else:
            # Let the base class handle StartFrame, EndFrame, SystemFrames, etc.
            # This ensures __started is set to True and frames are pushed correctly.
            await super().process_frame(frame, direction)

class MumbleTransport(BaseTransport):
    def __init__(self, mumble_client, params: TransportParams):
        super().__init__()
        self._mumble = mumble_client
        self._params = params
        self._input: Optional[MumbleInputTransport] = None
        self._output: Optional[MumbleOutputTransport] = None
        
        # Register supported events
        self._register_event_handler("on_connected")
        self._register_event_handler("on_disconnected")

    def input(self) -> FrameProcessor:
        if not self._input:
            self._input = MumbleInputTransport(self._mumble, self._params)
        return self._input

    def output(self) -> FrameProcessor:
        if not self._output:
            self._output = MumbleOutputTransport(self._mumble, self._params)
        return self._output

    async def start(self, frame: StartFrame):
        if self._input:
            await self._input.start(frame)
        if self._output:
            await self._output.start(frame)
        
        # Trigger on_connected when the transport is started within the pipeline
        await self._call_event_handler("on_connected", self._mumble)
