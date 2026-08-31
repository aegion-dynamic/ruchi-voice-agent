import asyncio
import base64
import json
import logging
import os
import time
from urllib.parse import urlencode

import websockets

from livekit.agents import APIConnectOptions
from livekit.agents.tts import AudioEmitter, SynthesizeStream, TTS, TTSCapabilities
from livekit.agents.utils import shortuuid

logger = logging.getLogger("ruchi-elevenlabs")

SAMPLE_RATE = 24_000
NUM_CHANNELS = 1


class ElevenLabsV3ConversationalTTS(TTS):
    """Direct ElevenLabs Eleven v3 Conversational TTS.

    This intentionally bypasses livekit.plugins.elevenlabs and talks directly
    to ElevenLabs' Text-to-Dialogue WebSocket.

    ElevenLabs is requested to return raw PCM at 24 kHz mono, which means the
    LiveKit AudioEmitter can forward the bytes without an MP3 decoder.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice_id: str | None = None,
        model_id: str = "eleven_v3_conversational",
        language_code: str = "te",
    ) -> None:
        self._api_key = api_key or os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
        self._voice_id = voice_id or os.getenv("ELEVEN_VOICE_ID")
        self._model_id = model_id or os.getenv(
            "ELEVEN_MODEL_ID", "eleven_v3_conversational"
        )
        self._language_code = language_code

        if not self._api_key:
            raise ValueError("ELEVEN_API_KEY is missing from .env")
        if not self._voice_id:
            raise ValueError("ELEVEN_VOICE_ID is missing from .env")
        if not self._model_id.startswith("eleven_v3"):
            raise ValueError(
                "ElevenLabs Text-to-Dialogue requires an Eleven v3 model; "
                f"got {self._model_id!r}"
            )

        super().__init__(
            capabilities=TTSCapabilities(streaming=True, aligned_transcript=False),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )

    @property
    def model(self) -> str:
        return self._model_id

    @property
    def provider(self) -> str:
        return "ElevenLabs Direct Text-to-Dialogue"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(
            max_retry=0, timeout=20.0
        ),
    ):
        return self._synthesize_with_stream(text=text, conn_options=conn_options)

    def stream(
        self,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(
            max_retry=0, timeout=20.0
        ),
    ) -> SynthesizeStream:
        return _ElevenLabsV3Stream(tts=self, conn_options=conn_options)


class _ElevenLabsV3Stream(SynthesizeStream):
    def __init__(
        self,
        *,
        tts: ElevenLabsV3ConversationalTTS,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts, conn_options=conn_options)
        self._tts = tts

    async def _run(self, output_emitter: AudioEmitter) -> None:
        request_id = shortuuid()

        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",
            frame_size_ms=20,
            stream=True,
        )
        output_emitter.start_segment(segment_id=request_id)

        query = urlencode(
            {
                "model_id": self._tts._model_id,
                "output_format": f"pcm_{SAMPLE_RATE}",
                "language_code": self._tts._language_code,
            }
        )
        url = (
            "wss://api.elevenlabs.io/v1/text-to-dialogue/stream-input?"
            + query
        )

        logger.info(
            "[TTS] ElevenLabs v3 direct WebSocket: model=%s",
            self._tts._model_id,
        )

        started = time.perf_counter()
        first_audio_logged = False
        send_finished = asyncio.Event()

        async with websockets.connect(
            url,
            open_timeout=self._conn_options.timeout,
            close_timeout=5,
            ping_interval=20,
            ping_timeout=20,
            max_size=None,
        ) as ws:
            # Official TTD protocol: register the voice and authenticate.
            await ws.send(
                json.dumps(
                    {
                        "voices": [self._tts._voice_id],
                        "xi_api_key": self._tts._api_key,
                    }
                )
            )

            async def send_task() -> None:
                nonlocal send_finished

                # After a flush, the next text starts a new dialogue turn.
                new_turn = False
                sent_any_text = False

                try:
                    async for item in self._input_ch:
                        if isinstance(item, self._FlushSentinel):
                            if sent_any_text:
                                await ws.send(json.dumps({"flush": True}))
                                new_turn = True
                            continue

                        text = item
                        if not text:
                            continue

                        sent_any_text = True
                        self._mark_started()

                        payload = {
                            "inputs": [
                                {
                                    "text": text,
                                    "voice_id": self._tts._voice_id,
                                }
                            ]
                        }

                        if new_turn:
                            payload["inputs"][0]["new_turn"] = True
                            new_turn = False

                        await ws.send(json.dumps(payload))

                finally:
                    # LiveKit calls end_input() at the end of the utterance.
                    # close_socket flushes remaining text and tells ElevenLabs
                    # to send the final frame. Even an empty stream must close,
                    # otherwise the receiver would wait indefinitely.
                    await ws.send(json.dumps({"close_socket": True}))
                    send_finished.set()

            async def receive_task() -> None:
                nonlocal first_audio_logged

                while True:
                    raw = await asyncio.wait_for(
                        ws.recv(),
                        timeout=self._conn_options.timeout,
                    )

                    if isinstance(raw, bytes):
                        logger.warning("[TTS] Unexpected binary WebSocket frame")
                        continue

                    message = json.loads(raw)

                    if message.get("error"):
                        raise RuntimeError(
                            f"ElevenLabs error: {message['error']}"
                        )

                    audio_b64 = message.get("audio")
                    if audio_b64:
                        pcm = base64.b64decode(audio_b64)

                        if not first_audio_logged:
                            first_audio_logged = True
                            logger.info(
                                "[TTS] First audio: %.0f ms",
                                (time.perf_counter() - started) * 1000,
                            )

                        output_emitter.push(pcm)

                    # is_final means all audio for this WebSocket is done.
                    if message.get("is_final"):
                        break

                    # If the server marks the current turn final but keeps
                    # the connection alive, keep listening for another turn.
                    if message.get("is_final_audio_for_turn"):
                        continue

            send = asyncio.create_task(send_task(), name="ruchi-eleven-send")
            receive = asyncio.create_task(
                receive_task(), name="ruchi-eleven-receive"
            )

            try:
                await asyncio.gather(send, receive)
            finally:
                for task in (send, receive):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(send, receive, return_exceptions=True)

        output_emitter.end_input()

        logger.debug(
            "[TTS] ElevenLabs utterance complete in %.0f ms",
            (time.perf_counter() - started) * 1000,
        )
