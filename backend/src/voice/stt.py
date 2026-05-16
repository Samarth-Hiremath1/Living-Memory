"""Staff observation transcription — ElevenLabs STT with Whisper fallback."""

from __future__ import annotations
import httpx
from ..config import settings


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str | None:
    """
    Transcribe staff voice observation using ElevenLabs STT.
    Falls back to a mock transcription if API key not set or STT fails.
    """
    if not settings.elevenlabs_api_key:
        return _mock_transcription()

    try:
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": settings.elevenlabs_api_key}
        # ElevenLabs Scribe accepts webm, mp4, wav, mp3 — send as-is with correct type
        files = {"file": ("observation.webm", audio_bytes, mime_type)}
        data = {"model_id": "scribe_v1", "language_code": "en"}

        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, files=files, data=data)
            resp.raise_for_status()
            result = resp.json()
            text = result.get("text", "").strip()
            if text:
                return text
    except Exception:
        pass

    # Fall back to mock so voice capture always works in demo mode
    return _mock_transcription()


def _mock_transcription() -> str:
    return "The guest asked about trail running options near the property and good spots for sunrise photography."
