"""Optional: Convert manager dossiers to audio for the morning briefing."""

from __future__ import annotations
import httpx
from ..config import settings


def dossier_to_audio(dossier_text: str, output_path: str | None = None) -> bytes | None:
    """
    Convert a dossier to audio using ElevenLabs TTS.
    Returns audio bytes, or None if not configured.
    """
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        return None

    # Trim to key sections for audio — full dossier is too long
    lines = dossier_text.split("\n")
    audio_lines = [l for l in lines if l.strip() and not l.startswith("##")]
    audio_text = "\n".join(audio_lines[:20])  # first ~20 lines

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
        headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": audio_text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.7, "similarity_boost": 0.8, "speed": 0.9},
        }

        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            audio_bytes = resp.content

        if output_path:
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

        return audio_bytes

    except Exception:
        return None
