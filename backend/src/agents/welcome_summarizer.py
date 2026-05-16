"""Welcome Summarizer: extracts preferences and structured data from the pre-arrival conversation."""

from __future__ import annotations
import json
import anthropic

from ..config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SUMMARY_PROMPT = """You are a Rosewood Concierge. You have just listened to a pre-arrival conversation between a guest and our Welcome Ambassador at Rosewood Sand Hill.

Your task is to extract 3-4 bullet points of 'captured' preferences or notes that will be shown to the guest as a warm summary of what we've learned — so they feel genuinely heard.

Use warm, professional language. Focus on what they are looking for, their journey, and their specific desires.

Format: JSON array of short strings (each under 60 characters).
Example: ["Oak grove walk on arrival afternoon", "Natural wine selection in room", "Quiet, unhurried pace throughout stay"]

Conversation transcript:
{{TRANSCRIPT}}
"""

_PREFERENCES_PROMPT = """You are analyzing a pre-arrival conversation between a Rosewood guest and our Welcome Ambassador. Extract structured preference data to personalize the guest's stay.

Output ONLY valid JSON with these fields (omit any you can't confidently infer):
{
  "interests": ["list of activities, passions, things they mentioned"],
  "pace": "unhurried | restorative | active | social | efficient",
  "arrival_mood": "tired | excited | neutral | stressed | celebratory",
  "room_temperature_f": 68,
  "dietary": ["any dietary mentions"],
  "special_occasion": "anniversary | birthday | business | retreat | null",
  "wine_preference": "natural wine | Burgundy | Napa | etc or null",
  "activity_interests": ["spa", "hiking", "wine tasting", "etc"],
  "placemaker_match": "Natalie Cheng | Reylon Agustin | David Park | null",
  "notes": "One sentence of anything important that doesn't fit above."
}

Only include fields you can infer with confidence. Do not guess.

Conversation transcript:
{{TRANSCRIPT}}
"""


def summarize_welcome_transcript(transcript: str) -> list[str]:
    """Return 3-4 warm bullet-point strings for the guest's 'Captured' UI panel."""
    if not transcript:
        return []

    response = _client.messages.create(
        model=settings.fast_model,
        max_tokens=300,
        system=_SUMMARY_PROMPT.replace("{{TRANSCRIPT}}", transcript),
        messages=[{"role": "user", "content": "Please summarize."}],
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        if isinstance(result, list):
            return [str(s) for s in result[:4]]
    except Exception:
        pass

    return []


def extract_preferences_from_transcript(transcript: str) -> dict:
    """
    Extract structured guest preferences from the welcome call transcript.
    Returns a dict suitable for merging into guest.preferences.
    """
    if not transcript:
        return {}

    response = _client.messages.create(
        model=settings.fast_model,
        max_tokens=500,
        system=_PREFERENCES_PROMPT.replace("{{TRANSCRIPT}}", transcript),
        messages=[{"role": "user", "content": "Please extract preferences."}],
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except Exception:
        pass

    return {}
