import asyncio
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlencode

import websockets
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVEN_VOICE_ID")
MODEL_ID = os.getenv("ELEVEN_MODEL_ID", "eleven_v3_conversational")

if not API_KEY:
    raise SystemExit("Missing ELEVEN_API_KEY")
if not VOICE_ID:
    raise SystemExit("Missing ELEVEN_VOICE_ID")

URL = (
    "wss://api.elevenlabs.io/v1/text-to-dialogue/stream-input?"
    + urlencode(
        {
            "model_id": MODEL_ID,
            "output_format": "pcm_24000",
            "language_code": "te",
        }
    )
)

TEXT = "నమస్కారం! నేను రుచి. ఈరోజు ఏం వండుకుందాం?"

async def main():
    output = bytearray()

    async with websockets.connect(
        URL,
        open_timeout=15,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
        max_size=None,
    ) as ws:
        await ws.send(json.dumps({
            "voices": [VOICE_ID],
            "xi_api_key": API_KEY,
        }))
        await ws.send(json.dumps({
            "inputs": [{"text": TEXT, "voice_id": VOICE_ID}]
        }))
        await ws.send(json.dumps({"flush": True}))

        async for raw in ws:
            if isinstance(raw, bytes):
                continue

            msg = json.loads(raw)

            if msg.get("error"):
                raise RuntimeError(msg["error"])

            if msg.get("audio"):
                output.extend(base64.b64decode(msg["audio"]))

            if msg.get("is_final_audio_for_turn"):
                await ws.send(json.dumps({"close_socket": True}))

            if msg.get("is_final"):
                break

    out = Path("eleven_test.pcm")
    out.write_bytes(output)
    print(f"OK: received {len(output)} bytes -> {out}")
    print("PCM format: signed 16-bit, mono, 24000 Hz")

if __name__ == "__main__":
    asyncio.run(main())
