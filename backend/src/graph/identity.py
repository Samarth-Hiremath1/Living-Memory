"""Cross-property identity resolution using Claude."""

from __future__ import annotations
import json
import anthropic

from ..config import settings
from .schema import Guest
from .store import graph


_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _profile_summary(g: Guest) -> dict:
    return {
        "name": g.name,
        "email": g.email,
        "phone": g.phone,
        "nationality": g.nationality,
        "home_city": g.home_city,
        "languages": g.languages,
    }


def are_same_person(g1: Guest, g2: Guest) -> tuple[bool, float, str]:
    """
    Ask Claude whether two guest profiles from different properties are the same person.
    Returns (is_same, confidence_0_to_1, reasoning).
    """
    prompt = f"""You are a hotel identity resolution assistant.

Given two guest profiles from different Rosewood properties, decide if they are the same person.

Profile A:
{json.dumps(_profile_summary(g1), indent=2)}

Profile B:
{json.dumps(_profile_summary(g2), indent=2)}

Respond in JSON only:
{{
  "same_person": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "one sentence explanation"
}}

Rules:
- Matching email = same person (confidence 0.99)
- Matching phone = same person (confidence 0.95)
- Name + nationality + home_city match = likely same (confidence 0.75)
- Name only = not enough (confidence < 0.5)
- When in doubt, return false"""

    response = _client.messages.create(
        model=settings.fast_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        result = json.loads(response.content[0].text)
        return result["same_person"], result["confidence"], result["reasoning"]
    except Exception:
        return False, 0.0, "Parse error"


def find_cross_property_duplicates() -> list[tuple[Guest, Guest, float, str]]:
    """Scan all guests and return likely duplicate pairs across different properties."""
    guests = graph.list_guests()
    duplicates = []
    seen = set()

    for i, g1 in enumerate(guests):
        for g2 in guests[i + 1:]:
            pair_key = tuple(sorted([g1.id, g2.id]))
            if pair_key in seen:
                continue
            seen.add(pair_key)

            # Quick pre-filter: skip if same property only
            g1_props = set(g1.property_aliases.keys())
            g2_props = set(g2.property_aliases.keys())
            if not g1_props or not g2_props:
                continue

            is_same, confidence, reasoning = are_same_person(g1, g2)
            if is_same and confidence >= 0.75:
                duplicates.append((g1, g2, confidence, reasoning))

    return duplicates


def merge_guest_profiles(primary: Guest, duplicate: Guest) -> Guest:
    """Merge duplicate into primary, preserving all cross-property signals."""
    # Merge property aliases
    primary.property_aliases.update(duplicate.property_aliases)

    # Merge stays (avoid duplicates)
    for stay_id in duplicate.stays:
        if stay_id not in primary.stays:
            primary.stays.append(stay_id)
            # Update the stay's guest_id to point to primary
            stay = graph.get_stay(stay_id)
            if stay:
                stay.guest_id = primary.id
                graph.upsert_stay(stay)

    # Merge preferences
    for k, v in duplicate.preferences.items():
        if k not in primary.preferences:
            primary.preferences[k] = v

    # Take the highest consent level
    consent_order = ["standard", "remembered", "living_memory"]
    if consent_order.index(duplicate.consent_level) > consent_order.index(primary.consent_level):
        primary.consent_level = duplicate.consent_level

    graph.upsert_guest(primary)
    return primary
