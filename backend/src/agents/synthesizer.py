"""Synthesizer: composes the full arrival plan from all agent outputs."""

from __future__ import annotations
import json
from pathlib import Path
import anthropic

from ..config import settings
from ..graph.schema import Guest, Stay, ArrivalPlan, Property
from ..graph.store import graph
from .friend_filter import filter_insights

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_PROMPT = (Path(__file__).parent.parent / "prompts" / "synthesizer.md").read_text()


def run_synthesizer(
    guest: Guest,
    stay: Stay,
    flight_result: dict,
    history: dict,
    place_result: dict,
    wellness: dict,
    welcome_transcript: str | None = None,
) -> ArrivalPlan:
    prop = graph.get_property(stay.property_id)

    # Friend-filter the history patterns before feeding to synthesizer
    raw_patterns = history.get("patterns", [])
    filtered_patterns = filter_insights(raw_patterns) if raw_patterns else []

    payload = {
        "guest": {
            "name": guest.name,
            "nationality": guest.nationality,
            "home_city": guest.home_city,
            "languages": guest.languages,
        },
        "stay": {
            "property_id": stay.property_id,
            "property_name": prop.name if prop else stay.property_id,
            "check_in": stay.check_in,
            "check_out": stay.check_out,
            "room_type": stay.room_type,
            "occasions": stay.occasions,
        },
        "flight": flight_result,
        "history": {
            **history,
            "patterns": filtered_patterns,
        },
        "placemaker_match": place_result,
        "wellness": wellness,
        "welcome_transcript": welcome_transcript,
        "property_context": {
            "character": prop.character if prop else "",
            "welcome_amenity_options": prop.welcome_amenity_options if prop else [],
            "room_amenity_options": prop.room_amenity_options if prop else [],
            "cultural_calendar": prop.cultural_calendar if prop else [],
        } if prop else {},
    }

    response = _client.messages.create(
        model=settings.orchestrator_model,
        max_tokens=2048,
        system=_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
    except Exception:
        result = {}

    # Build the ArrivalPlan
    plan = ArrivalPlan(
        guest_id=guest.id,
        stay_id=stay.id,
        property_id=stay.property_id,
        room_temperature_f=result.get("room_temperature_f", 68),
        welcome_amenity=result.get("welcome_amenity"),
        moments_to_create=result.get("moments_to_create", []),
        itinerary=result.get("itinerary", []),
        placemaker_intro=result.get("placemaker_intro"),
        flight_status=result.get("flight_status"),
        jet_lag_note=result.get("jet_lag_note"),
        raw_dossier=result.get("dossier_markdown", ""),
    )

    graph.upsert_arrival_plan(plan)
    return plan
