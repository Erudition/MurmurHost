import asyncio
import os
import pymumble_py3
import pymumble_py3.constants
import audioop

from pipecat.frames.frames import InputAudioRawFrame, StartFrame, OutputAudioRawFrame, Frame
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import TransportParams
from pipecat.processors.frame_processor import FrameDirection
from loguru import logger

class MumbleInputTransport(BaseInputTransport):
    def __init__(self, params: TransportParams, **kwargs):
        super().__init__(params, **kwargs)
        self._mumble = None
        self._loop = None
        self._input_ready = False
        self._audio_queue = asyncio.Queue()
        self._producer_task = None
        self._myself_session = None
        self._resample_state = None # Persistent state for ratecv

    def set_mumble(self, mumble, loop):
        self._mumble = mumble
        self._loop = loop
        self._audio_queue = asyncio.Queue()

    async def _producer_loop(self):
        """Drains the internal queue and pushes frames to the pipeline."""
        logger.debug(f"MumbleInput: Producer loop starting on loop {id(asyncio.get_running_loop())}")
        count = 0
        while self._input_ready:
            try:
                frame = await self._audio_queue.get()
                count += 1
                if count <= 10 or count % 50 == 0:
                    logger.debug(f"MumbleInput: Pushing frame #{count} (size: {len(frame.audio)}) to pipeline")
                await self.push_audio_frame(frame)
                self._audio_queue.task_done()
            except Exception as e:
                logger.error(f"MumbleInput producer error: {e}", exc_info=True)

    async def start(self, frame: StartFrame):
        logger.debug("MumbleInput: Initializing transport")
        self._loop = asyncio.get_running_loop()
        self._input_ready = True
        
        # Identify our own session ID for filtering
        if self._mumble and self._mumble.users.myself:
            self._myself_session = self._mumble.users.myself['session']
            logger.info(f"MumbleInput: Identified self session ID {self._myself_session} for filtering")

        # Start the background producer
        self._producer_task = asyncio.create_task(self._producer_loop())

        # MUST call super().start() to initialize internal Pipecat task management and linking
        await super().start(frame)
        await self.set_transport_ready(frame)
        logger.info(f"MumbleInput started on loop {id(self._loop)}")

    async def stop(self):
        self._input_ready = False
        if hasattr(self, "_producer_task"):
            self._producer_task.cancel()
        await super().stop()

    _sound_log_counter = 0

    def _on_sound_received(self, user, sound):
        # 1. Filter out self-audio
        if self._myself_session is not None and user['session'] == self._myself_session:
            return

        MumbleInputTransport._sound_log_counter += 1
        
        if not self._input_ready or not self._loop:
            return

        try:
            # 2. Extract RAW PCM from Mumble (48kHz mono)
            raw_audio = sound.pcm
            
            # 3. Resample to 16kHz (width=2, channels=1)
            # CRITICAL: Maintain state to avoid boundary clicks that disrupt VAD
            audio_16k, self._resample_state = audioop.ratecv(
                raw_audio, 2, 1, 48000, 16000, self._resample_state
            )
            
            # 3b. Use NATURAL gain (1.0x) to avoid clipping.
            audio_final = audio_16k # No boost

            frame = InputAudioRawFrame(audio_final, 16000, 1)
            
            # 4. Push to the internal queue WITHOUT blocking the Mumble thread
            # Use call_soon_threadsafe because asyncio.Queue is not thread-safe!
            self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, frame)

            if MumbleInputTransport._sound_log_counter <= 10 or MumbleInputTransport._sound_log_counter % 50 == 0:
                 username = user.get('name', f"ID:{user['session']}")
                 logger.debug(f"SOUND RECEIVED #{MumbleInputTransport._sound_log_counter} from {username} (PCM Len: {len(raw_audio)})")

        except Exception as e:
            logger.error(f"MumbleInput Callback Error on packet #{MumbleInputTransport._sound_log_counter}: {e}", exc_info=True)




class MumbleOutputTransport(BaseOutputTransport):
    def __init__(self, params: TransportParams, **kwargs):
        super().__init__(params, **kwargs)
        self._mumble = None

    def set_mumble(self, mumble):
        self._mumble = mumble

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # TOTAL INTAKE DEBUG
        logger.debug(f"MumbleOutput: INTAKE frame {type(frame).__name__} from {direction}")
        await super().process_frame(frame, direction)
        
        # Handle audio output frames
        if isinstance(frame, OutputAudioRawFrame):
            await self.write_output_audio_frame(frame)

    _output_count = 0

    async def write_output_audio_frame(self, frame: OutputAudioRawFrame):
        try:
            MumbleOutputTransport._output_count += 1
            if MumbleOutputTransport._output_count <= 10 or MumbleOutputTransport._output_count % 50 == 0:
                logger.debug(f"MumbleOutput: Writing frame #{MumbleOutputTransport._output_count} (source rate: {frame.sample_rate})")
            
            # 1. Apply safety gain boost (2.0x) for clarity
            boosted_audio = audioop.mul(frame.audio, 2, 2.0)

            # 2. Resample from Gemini (usually 24k) to 48k for Mumble
            audio_48k, _ = audioop.ratecv(boosted_audio, 2, 1, frame.sample_rate, 48000, None)
            
            await self.write_raw_audio_frames(audio_48k)
        except Exception as e:
            logger.error(f"MumbleOutput ERROR in write_output_audio_frame: {e}")

    async def write_raw_audio_frames(self, frames: bytes):
        # SDK Bypass: Guaranteed delivery path. Rely on sound_output existence instead of is_ready()
        if self._mumble and hasattr(self._mumble, "sound_output") and self._mumble.sound_output:
            self._mumble.sound_output.add_sound(frames)
        else:
            logger.warning(f"MumbleOutput: DROPPED {len(frames)} bytes because SoundOutput is not available")


class MumbleTransport:
    def __init__(self, mumble, params: TransportParams):
        self._params = params
        self._input = MumbleInputTransport(params)
        self._output = MumbleOutputTransport(params)
        self._mumble = mumble
        
        # Link mumble to sub-transports
        # Note: Loop will be captured in input.start()
        self._input.set_mumble(self._mumble, None)
        self._output.set_mumble(self._mumble)
        
        # Set callback for audio input
        self._mumble.callbacks.set_callback(
            pymumble_py3.constants.PYMUMBLE_CLBK_SOUNDRECEIVED,
            self._input._on_sound_received
        )

    def input(self):
        return self._input

    def output(self):
        return self._output
