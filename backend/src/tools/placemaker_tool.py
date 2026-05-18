"""
PlaceMaker search — query the internal graph store for property experts
(chefs, sommeliers, wellness directors, etc.) by interest keywords.

Unlike the other tools (which hit external APIs), this one queries
Living Memory's own knowledge graph — letting the agent reason over
both real-time external data and the system's internal state.
"""

from __future__ import annotations

import re

from ..graph.store import graph


# Stop words we won't bother scoring against
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "with", "who", "what",
    "loves", "love", "loving", "interested", "in", "to", "of", "is", "are",
    "guest", "guests", "someone", "person", "people", "looking", "wants",
}


def _tokens(text: str) -> set[str]:
    """Lowercase word tokens from a string, minus stopwords and very short words."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def find_placemaker(interests: str, property_id: str = "sand-hill") -> str:
    """
    Search PlaceMakers at a property by guest interests or query text.

    Args:
        interests:   Free-text description of guest interests, e.g.
                     "natural wine, Napa, slow afternoon" or
                     "long-haul fatigue, needs to decompress"
        property_id: Property to search (default: "sand-hill")

    Returns the top 3 ranked matches with their offerings.
    Score is the number of overlapping keywords between the query and
    each PlaceMaker's role, bio, offerings, and ideal_guest_profiles.
    """
    if not interests or not interests.strip():
        return "Error: interest description cannot be empty."

    placemakers = graph.get_placemakers_for_property(property_id)
    if not placemakers:
        prop = graph.get_property(property_id)
        if prop is None:
            return f"No property found with id '{property_id}'."
        return f"No PlaceMakers configured for {prop.name}."

    query_tokens = _tokens(interests)
    if not query_tokens:
        return f"Could not extract searchable keywords from '{interests}'."

    # Score each PlaceMaker by keyword overlap
    scored: list[tuple[int, list[str], object]] = []
    for pm in placemakers:
        offering_text = " ".join(
            f"{o.get('name', '')} {o.get('description', '')} {o.get('best_for', '')}"
            for o in (pm.offerings or [])
        )
        ideal_text = " ".join(pm.ideal_guest_profiles or [])
        haystack = f"{pm.role} {pm.bio or ''} {offering_text} {ideal_text}"
        pm_tokens = _tokens(haystack)

        overlap = query_tokens & pm_tokens
        if overlap:
            scored.append((len(overlap), sorted(overlap), pm))

    if not scored:
        return (
            f"No PlaceMakers at {property_id} match '{interests}'. "
            f"Available: {', '.join(pm.name for pm in placemakers)}."
        )

    scored.sort(key=lambda x: -x[0])
    top = scored[:3]

    lines = [f"PlaceMakers at {property_id} matching '{interests}':"]
    for score, matched_terms, pm in top:
        # Pick the two most relevant offerings to mention
        offerings_summary = []
        for o in (pm.offerings or [])[:3]:
            name = o.get("name", "")
            dur = o.get("duration") or o.get("best_time") or ""
            if name:
                offerings_summary.append(f"{name}" + (f" ({dur})" if dur else ""))
        offerings_str = "; ".join(offerings_summary) if offerings_summary else "no listed offerings"

        lines.append(
            f"• {pm.name} — {pm.role}. "
            f"Matched on: {', '.join(matched_terms)}. "
            f"Offerings: {offerings_str}."
        )

    return "\n".join(lines)
