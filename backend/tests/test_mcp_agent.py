"""
Eval suite for the MCP tool-use agent — hospitality concierge edition.

Three tools are exposed to the agent:
  • get_weather         — current conditions for any city
  • get_flight_status   — live IATA flight lookup with jet-lag severity
  • find_placemaker     — search the property's internal expert roster

Two layers of tests:
  1. Unit tests        — each tool function called directly. No LLM, no API key.
  2. Integration tests — the full LangGraph agent against real APIs. Require
                         ANTHROPIC_API_KEY in the environment.

Run all:
    cd backend && pytest tests/test_mcp_agent.py -v

Unit only:
    pytest tests/test_mcp_agent.py -v -m "not integration"

Integration only:
    pytest tests/test_mcp_agent.py -v -m integration -s
"""

from __future__ import annotations

import os
import textwrap

import pytest

from src.tools.flight_status_tool import get_flight_info
from src.tools.placemaker_tool import find_placemaker
from src.tools.weather_tool import get_weather

# ── Markers ───────────────────────────────────────────────────────────────────

integration = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration tests",
)


# ── Unit tests: weather ───────────────────────────────────────────────────────


class TestWeather:
    def test_returns_string(self):
        result = get_weather("London")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_contains_temperature(self):
        result = get_weather("Tokyo")
        # Either real data (has degree symbol) or an error string
        assert "°" in result or "error" in result.lower()

    def test_empty_location(self):
        result = get_weather("")
        assert "error" in result.lower()

    def test_nonsense_location_graceful(self):
        # Should return an error string, not raise
        result = get_weather("xkqzpwrt12345")
        assert isinstance(result, str)


# ── Unit tests: flight status ─────────────────────────────────────────────────


class TestFlightStatus:
    def test_returns_string(self):
        # Falls back to demo flight (Lufthansa FRA→SFO) when AviationStack is unset
        result = get_flight_info("LH456")
        assert isinstance(result, str)
        assert len(result) > 20

    def test_contains_route_info(self):
        result = get_flight_info("LH456")
        # Demo flight is FRA → SFO
        assert "FRA" in result or "SFO" in result or "Frankfurt" in result.lower()

    def test_contains_jet_lag_note(self):
        # FRA → SFO is ~9 hours difference → significant jet lag
        result = get_flight_info("LH456")
        assert (
            "jet lag" in result.lower()
            or "long-haul" in result.lower()
            or "fatigue" in result.lower()
        )

    def test_empty_flight_number(self):
        result = get_flight_info("")
        assert "error" in result.lower()

    def test_handles_lowercase(self):
        # Should normalise case
        result = get_flight_info("lh456")
        assert isinstance(result, str)
        assert len(result) > 20


# ── Unit tests: PlaceMaker search ─────────────────────────────────────────────


class TestPlaceMaker:
    def test_returns_string(self):
        result = find_placemaker("natural wine, Napa Valley")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_wine_query_finds_sommelier(self):
        # David Park is the wine curator at sand-hill
        result = find_placemaker("Napa wine tasting and small estates")
        assert "David" in result or "wine" in result.lower()

    def test_wellness_query_finds_natalie(self):
        # Natalie Cheng is the wellness director
        result = find_placemaker("long-haul fatigue, needs to decompress and recover")
        assert "Natalie" in result or "wellness" in result.lower() or "recovery" in result.lower()

    def test_food_query_finds_chef(self):
        # Reylon Agustin is the executive chef
        result = find_placemaker("food-curious guest who loves California cuisine")
        assert "Reylon" in result or "chef" in result.lower() or "food" in result.lower()

    def test_empty_interests(self):
        result = find_placemaker("")
        assert "error" in result.lower()

    def test_unknown_property(self):
        result = find_placemaker("wine", property_id="nonexistent-property")
        assert "no" in result.lower() or "error" in result.lower()

    def test_returns_offerings_for_match(self):
        result = find_placemaker("Napa wine")
        # Should mention at least one offering name (capitalised in the data)
        has_offering = any(
            keyword in result
            for keyword in ["Napa Day", "Cellar Tasting", "Sonoma", "Offerings"]
        )
        assert has_offering or "error" in result.lower() or "no" in result.lower()


# ── Integration eval cases ────────────────────────────────────────────────────
#
# Each case specifies:
#   query              — the input to the agent
#   expected_tools     — tools that MUST appear in tool_calls (subset match)
#   expected_keywords  — string (must appear) or list (any one must appear)
#   description        — human-readable label

EVAL_CASES = [
    {
        "id": "weather_arrival_planning",
        "description": "Weather for arrival planning",
        "query": "What's the weather like in Menlo Park right now? A guest is arriving this afternoon.",
        "expected_tools": ["get_weather"],
        "expected_keywords": ["°"],
    },
    {
        "id": "flight_status_basic",
        "description": "Inbound flight lookup",
        "query": "Can you check the status of flight LH456? A guest is on it.",
        "expected_tools": ["get_flight_status"],
        "expected_keywords": [["LH456", "Lufthansa", "Frankfurt"]],
    },
    {
        "id": "flight_jet_lag_aware",
        "description": "Flight lookup with jet lag implications",
        "query": (
            "A guest is flying in on LH456 from Frankfurt. "
            "What should we know about how they'll arrive?"
        ),
        "expected_tools": ["get_flight_status"],
        "expected_keywords": [["jet lag", "long-haul", "fatigue", "tired"]],
    },
    {
        "id": "placemaker_wine",
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
        "description": "PlaceMaker search — wellness / long-haul recovery",
        "query": (
            "A guest is arriving exhausted from a 14-hour flight from Asia. "
            "Who do we have at the property who can help them recover?"
        ),
        "expected_tools": ["find_placemaker"],
        "expected_keywords": [["Natalie", "Cheng", "wellness", "recovery"]],
    },
    {
        "id": "chained_flight_and_placemaker",
        "description": "Chained reasoning — flight then PlaceMaker match",
        "query": (
            "Guest is inbound on LH456. They mentioned they're "
            "passionate about California cuisine. Check the flight and tell "
            "me who at the property would be the right host."
        ),
        "expected_tools": ["get_flight_status", "find_placemaker"],
        "expected_keywords": [["Reylon", "chef", "Madera"]],
    },
    {
        "id": "no_tool_needed",
        "description": "Agent answers directly without any tool",
        "query": "What is the capital of France?",
        "expected_tools": [],
        "expected_keywords": [["Paris", "paris"]],
    },
]


@integration
@pytest.mark.integration
@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_agent_eval(case: dict) -> None:
    """Run the MCP agent on a single eval case and assert correctness."""
    from src.agents.mcp_agent import run_mcp_agent

    result = run_mcp_agent(case["query"])

    # ── 1. Agent must complete ──────────────────────────────────────────────
    assert result.final_answer, (
        f"[{case['id']}] Agent produced no answer.\n"
        f"Error: {result.error}\n"
        f"Tool calls: {result.tool_calls}"
    )

    # ── 2. No unhandled errors ──────────────────────────────────────────────
    assert not result.error, (
        f"[{case['id']}] Agent errored: {result.error}"
    )

    # ── 3. Tool selection ───────────────────────────────────────────────────
    tools_used = {call["tool"] for call in result.tool_calls}
    for expected_tool in case["expected_tools"]:
        assert expected_tool in tools_used, (
            f"[{case['id']}] Expected tool '{expected_tool}' was not called.\n"
            f"Tools used: {tools_used}\n"
            f"Answer: {result.final_answer[:300]}"
        )

    # ── 4. Answer content ───────────────────────────────────────────────────
    # Each entry is either a plain string (must appear) or a list of strings
    # (any one must appear — used for alternative phrasings / number formats).
    answer_lower = result.final_answer.lower()
    for kw_entry in case.get("expected_keywords", []):
        if isinstance(kw_entry, list):
            alternatives = kw_entry
            assert any(alt.lower() in answer_lower for alt in alternatives), (
                f"[{case['id']}] Expected one of {alternatives!r} in answer.\n"
                f"Answer: {result.final_answer[:300]}"
            )
        else:
            assert kw_entry.lower() in answer_lower, (
                f"[{case['id']}] Expected '{kw_entry}' in answer.\n"
                f"Answer: {result.final_answer[:300]}"
            )

    # ── 5. No infinite loops ────────────────────────────────────────────────
    assert result.steps_taken <= 6, (
        f"[{case['id']}] Agent took {result.steps_taken} steps — possible loop."
    )

    # Print a summary line for readable -s output
    tools_str = ", ".join(tools_used) if tools_used else "none"
    print(
        f"\n✓ [{case['id']}] {case['description']}\n"
        f"  Tools: {tools_str} | Steps: {result.steps_taken}\n"
        f"  Answer: {textwrap.shorten(result.final_answer, 140)}"
    )


@integration
@pytest.mark.integration
def test_agent_result_structure() -> None:
    """Verify the MCPAgentResult dataclass has the expected shape."""
    from src.agents.mcp_agent import MCPAgentResult, run_mcp_agent

    result = run_mcp_agent("What's the weather in Paris?")
    assert isinstance(result, MCPAgentResult)
    assert isinstance(result.final_answer, str)
    assert isinstance(result.tool_calls, list)
    assert isinstance(result.steps_taken, int)
    assert result.error is None


@integration
@pytest.mark.integration
def test_tool_call_log_populated() -> None:
    """Verify tool calls are logged with input and output when a tool is used."""
    from src.agents.mcp_agent import run_mcp_agent

    result = run_mcp_agent("Look up flight LH456.")
    assert result.tool_calls, "Expected a flight tool call."
    call = result.tool_calls[0]
    assert call["tool"] == "get_flight_status"
    assert "flight_number" in call["input"]
    # Output should mention the route or jet lag
    assert "FRA" in call["output"] or "Frankfurt" in call["output"]
