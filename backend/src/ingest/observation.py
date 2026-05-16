"""Convert raw staff observations into structured graph updates."""

from __future__ import annotations
import json
from pathlib import Path
import anthropic

from ..config import settings
from ..graph.schema import Observation, ObservationSource, Guest
from ..graph.store import graph

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_PROMPT = (Path(__file__).parent.parent / "prompts" / "observation_parser.md").read_text()


def parse_observation(
    raw_text: str,
    stay_id: str,
    guest_id: str,
    property_id: str,
    source: ObservationSource = ObservationSource.STAFF_VOICE,
    staff_id: str | None = None,
) -> tuple[Observation, dict]:
    """Parse raw observation text into a structured Observation + action items."""

    response = _client.messages.create(
        model=settings.fast_model,
        max_tokens=512,
        system=_PROMPT,
        messages=[{"role": "user", "content": raw_text}],
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
    except Exception:
        parsed = {"summary": raw_text, "tags": [], "action_items": [], "sentiment": "neutral"}

    obs = Observation(
        stay_id=stay_id,
        guest_id=guest_id,
        property_id=property_id,
        raw_text=raw_text,
        structured=parsed,
        tags=parsed.get("tags", []),
        source=source,
        staff_id=staff_id,
        sentiment=parsed.get("sentiment"),
    )

    graph.add_observation(obs)

    # Update guest interests/preferences if new signals found
    guest = graph.get_guest(guest_id)
    if guest:
        interests = parsed.get("interests_revealed", [])
        for interest in interests:
            if "interests" not in guest.preferences:
                guest.preferences["interests"] = []
            if interest not in guest.preferences["interests"]:
                guest.preferences["interests"].append(interest)
        if interests:
            graph.upsert_guest(guest)

    # Normalize action_items — Claude returns objects {department, action, urgency};
    # frontend expects plain strings.
    raw_items = parsed.get("action_items", [])
    action_items: list[str] = []
    for item in raw_items:
        if isinstance(item, str):
            action_items.append(item)
        elif isinstance(item, dict):
            action = item.get("action", "")
            dept = item.get("department", "")
            urgency = item.get("urgency", "")
            label = f"[{dept.title()}] {action}".strip() if dept else action
            if urgency and urgency == "now":
                label = f"⚡ {label}"
            action_items.append(label)
        else:
            action_items.append(str(item))

    return obs, action_items
