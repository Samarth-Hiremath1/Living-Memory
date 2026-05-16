"""PlaceMaker matching agent."""

from __future__ import annotations
import json
from pathlib import Path
import anthropic

from ..config import settings
from ..graph.schema import Guest, Property, PlaceMaker
from ..graph.store import graph

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_PROMPT = (Path(__file__).parent.parent / "prompts" / "place_agent.md").read_text()


def run_place_agent(guest: Guest, property_id: str, history: dict) -> dict:
    """Match guest to the right PlaceMaker at the given property."""
    prop = graph.get_property(property_id)
    placemakers = graph.get_placemakers_for_property(property_id)

    if not placemakers:
        return {
            "recommended_placemaker_id": None,
            "recommended_placemaker_name": None,
            "why": None,
            "suggested_offering": None,
            "timing_suggestion": None,
            "cultural_calendar_hook": None,
        }

    pm_list = [
        {
            "id": pm.id,
            "name": pm.name,
            "role": pm.role,
            "location": pm.location,
            "offerings": pm.offerings,
            "ideal_guest_profiles": pm.ideal_guest_profiles,
        }
        for pm in placemakers
    ]

    cultural_calendar = prop.cultural_calendar if prop else []

    payload = {
        "guest_name": guest.name,
        "guest_interests": history.get("interests", []),
        "guest_patterns": history.get("patterns", []),
        "guest_nationality": guest.nationality,
        "placemakers": pm_list,
        "cultural_calendar": cultural_calendar,
    }

    response = _client.messages.create(
        model=settings.orchestrator_model,
        max_tokens=512,
        system=_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return {
            "recommended_placemaker_id": None,
            "recommended_placemaker_name": None,
            "why": None,
            "suggested_offering": None,
            "timing_suggestion": None,
            "cultural_calendar_hook": None,
        }
