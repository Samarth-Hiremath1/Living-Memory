"""
Shared eval cases for the Concierge Research Agent.

Each case includes a `slice` tag for failure-mode analysis. The same list
is consumed by:
  - tests/test_mcp_agent.py   (pytest parametrize for pass/fail assertions)
  - eval/run_eval.py          (rubric-based LLM-as-judge scoring + report)

Slice taxonomy:
  single-tool-external  — one external API call (weather, flight)
  single-tool-internal  — one internal graph-store lookup (placemaker)
  multi-tool            — chains two or more tools to answer
  no-tool               — agent should answer directly without any tool
  ambiguous-query       — vague intent, agent must infer or ask
  degraded-api          — tool likely returns an error; tests graceful handling
"""

from __future__ import annotations


EVAL_CASES: list[dict] = [
    # ── single-tool external ─────────────────────────────────────────────────
    {
        "id": "weather_arrival_planning",
        "slice": "single-tool-external",
        "description": "Weather for arrival planning",
        "query": "What's the weather like in Menlo Park right now? A guest is arriving this afternoon.",
        "expected_tools": ["get_weather"],
        "expected_keywords": ["°"],
    },
    {
        "id": "flight_status_basic",
        "slice": "single-tool-external",
        "description": "Inbound flight lookup",
        "query": "Can you check the status of flight LH456? A guest is on it.",
        "expected_tools": ["get_flight_status"],
        "expected_keywords": [["LH456", "Lufthansa", "Frankfurt"]],
    },
    {
        "id": "flight_jet_lag_aware",
        "slice": "single-tool-external",
        "description": "Flight lookup with jet lag implications",
        "query": (
            "A guest is flying in on LH456 from Frankfurt. "
            "What should we know about how they'll arrive?"
        ),
        "expected_tools": ["get_flight_status"],
        "expected_keywords": [["jet lag", "long-haul", "fatigue", "tired"]],
    },

    # ── single-tool internal (graph retrieval) ───────────────────────────────
    {
        "id": "placemaker_wine",
        "slice": "single-tool-internal",
        "description": "PlaceMaker search — wine enthusiast",
        "query": (
            "I have a guest arriving who loves Napa wines and small "
            "family estates. Who at the property should host them?"
        ),
        "expected_tools": ["find_placemaker"],
        "expected_keywords": [["David", "Park", "sommelier", "wine"]],
    },
    {
        "id": "placemaker_wellness",
        "slice": "single-tool-internal",
        "description": "PlaceMaker search — wellness / long-haul recovery",
        "query": (
            "A guest is arriving exhausted from a 14-hour flight from Asia. "
            "Who do we have at the property who can help them recover?"
        ),
        "expected_tools": ["find_placemaker"],
        "expected_keywords": [["Natalie", "Cheng", "wellness", "recovery"]],
    },

    # ── multi-tool chaining ──────────────────────────────────────────────────
    {
        "id": "chained_flight_and_placemaker",
        "slice": "multi-tool",
        "description": "Chained reasoning — flight then PlaceMaker match",
        "query": (
            "Guest is inbound on LH456. They mentioned they're "
            "passionate about California cuisine. Check the flight and tell "
            "me who at the property would be the right host."
        ),
        "expected_tools": ["get_flight_status", "find_placemaker"],
        "expected_keywords": [["Reylon", "chef", "Madera"]],
    },

    # ── no tool needed ───────────────────────────────────────────────────────
    {
        "id": "no_tool_needed",
        "slice": "no-tool",
        "description": "Agent answers directly without any tool",
        "query": "What is the capital of France?",
        "expected_tools": [],
        "expected_keywords": [["Paris", "paris"]],
    },

    # ── ambiguous query — agent should ask or pick sensibly ─────────────────
    {
        "id": "ambiguous_vague_request",
        "slice": "ambiguous-query",
        "description": "Vague request — no clear tool fit",
        "query": "I have a guest arriving. What should I prepare?",
        # The agent could reasonably do nothing (ask for clarification) or
        # try find_placemaker — we don't enforce a specific choice.
        "expected_tools": [],
        # Expect either a clarifying question or a generic helpful response
        "expected_keywords": [["more", "specific", "tell", "interests", "name", "what", "share"]],
    },

    # ── degraded API — tool returns error; agent must handle gracefully ─────
    {
        "id": "degraded_api_bad_location",
        "slice": "degraded-api",
        "description": "Weather lookup for nonsense location — tool returns error",
        "query": "What's the weather in xkqzpwrt12345 right now?",
        "expected_tools": ["get_weather"],
        # Agent must recognise the error and report it, not fabricate
        "expected_keywords": [["could not", "couldn't", "error", "not find", "invalid", "unable", "no data"]],
    },
]


def get_case(case_id: str) -> dict | None:
    """Return a single case by id, or None if not found."""
    return next((c for c in EVAL_CASES if c["id"] == case_id), None)


def cases_by_slice(slice_tag: str) -> list[dict]:
    """Return all cases tagged with the given slice."""
    return [c for c in EVAL_CASES if c.get("slice") == slice_tag]


def all_slices() -> list[str]:
    """Return the deduplicated list of slice tags present in EVAL_CASES."""
    seen: list[str] = []
    for c in EVAL_CASES:
        s = c.get("slice", "unknown")
        if s not in seen:
            seen.append(s)
    return seen
