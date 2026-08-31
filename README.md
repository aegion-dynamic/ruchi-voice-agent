# Ruchi Voice Agent

A real-time conversational Telugu voice agent built with LiveKit, Sarvam, Google Gemini, and ElevenLabs.

## Architecture

The system separates the real-time conversation pipeline from speech synthesis:

```text
                         ┌──────────────────────┐
                         │        User          │
                         │   Microphone / Audio │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       LiveKit        │
                         │                      │
                         │ • Audio streaming   │
                         │ • VAD               │
                         │ • Turn detection    │
                         │ • Interruption      │
                         │ • Conversation flow │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Sarvam Saaras v3  │
                         │         STT          │
                         │                      │
                         │ Telugu speech → Text │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     Google Gemini    │
                         │         LLM          │
                         │                      │
                         │ Context + reasoning  │
                         │ → Response text      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │       ElevenLabs API         │
                    │            TTS               │
                    │                              │
                    │   Response text → Telugu    │
                    │        audio stream          │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                         ┌──────────────────────┐
                         │       LiveKit        │
                         │    Audio Output     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │        User          │
                         │   Hears AI response  │
                         └──────────────────────┘
```

### Pipeline

**User Audio → LiveKit VAD/Turn Detection → Sarvam STT → Gemini LLM → ElevenLabs TTS API → LiveKit Audio Output → User**

LiveKit handles the real-time voice-agent orchestration, audio streaming, VAD, turn detection, interruptions, and conversation flow. ElevenLabs is used separately for TTS through its API/WebSocket.

## Libraries & Packages

### Core

* **`livekit-agents`** — Real-time voice-agent framework, `AgentSession`, audio processing, VAD, turn detection, interruptions, and conversation orchestration.
* **`livekit-plugins-sarvam`** — Integration with Sarvam Saaras v3 for speech-to-text.
* **`livekit-plugins-google`** — Integration with Google Gemini for the LLM.
* **`python-dotenv`** — Loads environment variables and API keys from `.env`.
* **`aiohttp`** — Asynchronous HTTP and WebSocket communication, used for ElevenLabs streaming.
* **`websockets`** — WebSocket communication where required by the TTS implementation.

### Services

* **LiveKit** — Real-time audio and voice-agent infrastructure.
* **Sarvam Saaras v3** — Telugu/Indian-language speech recognition.
* **Google Gemini** — Conversational LLM.
* **ElevenLabs** — High-quality Telugu text-to-speech.

> `livekit-plugins-elevenlabs` is not required if ElevenLabs TTS is implemented directly through the ElevenLabs API/WebSocket.

## Project Structure

```text
ruchi/
├── agent.py              # Main LiveKit voice agent
├── eleven_tts.py         # ElevenLabs TTS integration
├── test_elevenlabs.py    # ElevenLabs testing
├── requirements.txt      # Python dependencies
├── .gitignore
└── README.md
```

## Runtime Flow

```text
User
 │
 │ Audio
 ▼
LiveKit
 │
 ├── VAD
 ├── Turn Detection
 ├── Interruption Handling
 └── Audio Streaming
 │
 ▼
Sarvam Saaras v3
 │
 │ Speech → Text
 ▼
Google Gemini
 │
 │ Text → Response
 ▼
ElevenLabs API / WebSocket
 │
 │ Text → Telugu Audio
 ▼
LiveKit
 │
 │ Audio Output
 ▼
User
```

## Goal

Build a low-latency, natural Telugu conversational voice assistant with real-time speech recognition, LLM processing, and high-quality Telugu speech synthesis.

## Setup

Create a Python virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the agent:

```bash
python agent.py console
```

The project is designed to run as a Python-based real-time voice agent and can later be connected to a LiveKit room/client for production deployment.
