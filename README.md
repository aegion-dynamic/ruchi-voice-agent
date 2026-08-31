# Ruchi Telugu Voice Agent

Pipeline:

LiveKit VAD → Sarvam Saaras v3 STT → Google Gemini → direct ElevenLabs Text-to-Dialogue WebSocket → LiveKit audio.

The LiveKit ElevenLabs plugin is intentionally NOT used.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your keys.

## Run

```bash
python agent.py console
```

If your installed LiveKit CLI recommends `lk agent console`, use that command instead.

## Required keys

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `SARVAM_API_KEY`
- `GOOGLE_API_KEY`
- `ELEVEN_API_KEY`
- `ELEVEN_VOICE_ID`

`ELEVEN_MODEL_ID` defaults to `eleven_v3_conversational`.

## Architecture

LiveKit owns the VAD, turn handling, interruption handling, STT/LLM orchestration and audio session.

The only custom provider bridge is:

Gemini text → ElevenLabs Text-to-Dialogue WebSocket → PCM 24 kHz → LiveKit AudioEmitter.

## Important

The ElevenLabs v3 Text-to-Dialogue WebSocket requires a v3 model and a registered voice. For `eleven_v3_conversational`, only one voice is registered per connection.

The code requests `pcm_24000`, so no MP3 decoder is required.
