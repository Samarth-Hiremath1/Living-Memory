"""Wellness agent: synthesizes recovery needs from mock signals. Never diagnoses."""

from __future__ import annotations
from ..graph.schema import Guest, Stay


# Mock wearable data — in production this would be an opt-in API integration
MOCK_WELLNESS_DATA: dict[str, dict] = {
    "anna-lindqvist": {
        "sleep_quality": "fair",   # fair/good/excellent
        "resting_hr_trend": "elevated",
        "travel_stress_signal": "high",
        "toggle_enabled": True,
    }
}


def get_wellness_signals(guest: Guest, stay: Stay) -> dict:
    """Return mock wellness signals for demo. Returns safe, surface-level signals only."""
    # In demo: look up by guest name slug
    name_slug = guest.name.lower().replace(" ", "-")
    raw = MOCK_WELLNESS_DATA.get(name_slug, {})

    if not raw or not raw.get("toggle_enabled", False):
        return {"available": False, "staff_note": None}

    # Translate signals into staff-facing language (never clinical)
    notes = []

    if raw.get("travel_stress_signal") == "high":
        notes.append("She's had a long journey — a calm, unhurried arrival will set the right tone.")

    if raw.get("sleep_quality") in ("fair", "poor"):
        notes.append("A quiet room away from any early morning noise would be a thoughtful touch.")

    return {
        "available": True,
        "staff_note": " ".join(notes) if notes else None,
        "recommend_spa_mention": raw.get("travel_stress_signal") == "high",
    }
