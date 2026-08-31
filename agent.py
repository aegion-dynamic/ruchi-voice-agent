import logging
import os

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    TurnHandlingOptions,
    cli,
    inference,
)
from livekit.plugins import google, sarvam

from eleven_tts import ElevenLabsV3ConversationalTTS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)

logger = logging.getLogger("ruchi")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


RUCHI_INSTRUCTIONS = """
You are Ruchi, a warm, friendly, natural Telugu cooking companion.

You should feel like a helpful elder sister cooking alongside the user.

PERSONALITY:
- Warm, friendly, patient, caring, encouraging, and natural.
- Never robotic, overly formal, or judgmental.

LANGUAGE:
- If the user speaks Telugu, respond in natural spoken Telugu.
- If the user speaks English, respond in English.
- If the user mixes Telugu and English, naturally mix Telugu and English.
- Understand Telugu spoken naturally even when transcription contains English words.
- Do not unnecessarily translate Telugu into English.
- Prefer conversational Telugu rather than textbook Telugu.

VOICE:
- Keep responses short, normally 1–3 sentences.
- Do not give long explanations unless the user asks.
- Do not dump large lists into speech.

COOKING:
- Help users cook step-by-step.
- For a multi-step recipe, give one major step at a time.
- Remember the current recipe and current step.
- If the user asks "what next?", continue from the current step.
- If the user says "done", "next", "okay", "continue", or "finished", continue naturally.
- If something goes wrong while cooking, calmly explain the simplest fix.

CORE PRINCIPLE:
Ruchi should feel like someone cooking alongside the user,
not a recipe website reading instructions aloud.
"""


class Ruchi(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=RUCHI_INSTRUCTIONS)

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Greet the user naturally in Telugu. Say exactly: "
                "నమస్కారం! నేను రుచి. ఈరోజు ఏం వండుకుందాం?"
            )
        )


async def entrypoint(ctx: JobContext) -> None:
    logger.info("[LIVEKIT] Starting Ruchi in room=%s", ctx.room.name)

    # Explicit local Silero VAD.
    # We use VAD turn detection rather than LiveKit's semantic turn detector
    # because the audio turn detector currently documents support for 14
    # languages and Telugu is not among them.
    vad = inference.VAD(
        model="silero",
        min_speech_duration=0.05,
        min_silence_duration=0.35,
        prefix_padding_duration=0.5,
        activation_threshold=0.5,
    )

    stt = sarvam.STT(
        language="te-IN",
        model="saaras:v3",
        mode="transcribe",
    )

    llm = google.LLM(
        model=GEMINI_MODEL,
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.7,
        max_output_tokens=256,
    )

    tts = ElevenLabsV3ConversationalTTS(
        api_key=os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY"),
        voice_id=os.getenv("ELEVEN_VOICE_ID"),
        model_id=os.getenv("ELEVEN_MODEL_ID", "eleven_v3_conversational"),
        language_code="te",
    )

    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        turn_handling=TurnHandlingOptions(
            turn_detection="vad",
            endpointing={
                "mode": "fixed",
                "min_delay": 0.30,
                "max_delay": 2.0,
            },
            interruption={
                "mode": "adaptive",
                "min_duration": 0.35,
                "resume_false_interruption": True,
            },
        ),
        preemptive_generation=False,
    )

    @session.on("user_input_transcribed")
    def on_user_transcript(event) -> None:
        if getattr(event, "is_final", False):
            logger.info("[STT] %s", getattr(event, "transcript", ""))

    await session.start(
        agent=Ruchi(),
        room=ctx.room,
    )

    logger.info(
        "[RUCHI] Ready: Sarvam STT → Gemini %s → ElevenLabs %s",
        GEMINI_MODEL,
        os.getenv("ELEVEN_MODEL_ID", "eleven_v3_conversational"),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
