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
# EVAL_CASES is the canonical eval set, defined in eval/cases.py so both this
# pytest suite and the rubric-scorer CLI consume the same source of truth.
# Each case includes a `slice` tag for failure-mode analysis.

from eval.cases import EVAL_CASES  # noqa: E402


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

    # ── 3. Tool selection, per the case's tool_policy ───────────────────────
    #
    # "required"  — every expected tool must have been called
    # "optional"  — graded on outcome only; any tool choice is acceptable
    # "forbidden" — no tool should have been called
    tools_used = {call["tool"] for call in result.tool_calls}
    policy = case.get("tool_policy", "required")

    if policy == "required":
        for expected_tool in case["expected_tools"]:
            assert expected_tool in tools_used, (
                f"[{case['id']}] Expected tool '{expected_tool}' was not called.\n"
                f"Tools used: {tools_used}\n"
                f"Answer: {result.final_answer[:300]}"
            )
    elif policy == "forbidden":
        assert not tools_used, (
            f"[{case['id']}] Expected NO tool calls but agent called: {tools_used}\n"
            f"Answer: {result.final_answer[:300]}"
        )
    # policy == "optional": deliberately no tool assertion. The case is graded
    # on the answer content below. This exists because asserting a specific tool
    # call encodes HOW the agent should work rather than WHETHER it worked.

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
    assert not result.hit_step_cap, (
        f"[{case['id']}] Agent was cut off by the step cap rather than finishing "
        f"on its own — the answer is truncated reasoning, not a real answer."
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


# ── Structural tests on the eval suite itself ────────────────────────────────
#
# These guard the harness, not the agent. They run without an API key.


class TestEvalSuiteShape:
    def test_case_count(self):
        assert len(EVAL_CASES) == 25, f"expected 25 cases, got {len(EVAL_CASES)}"

    def test_no_slice_under_three_cases(self):
        from eval.cases import slice_counts

        thin = {s: n for s, n in slice_counts().items() if n < 3}
        assert not thin, f"slices with fewer than 3 cases: {thin}"

    def test_case_ids_unique(self):
        ids = [c["id"] for c in EVAL_CASES]
        assert len(ids) == len(set(ids)), "duplicate case ids"

    def test_every_case_has_required_fields(self):
        for c in EVAL_CASES:
            for field_name in ("id", "slice", "description", "query", "expected_tools"):
                assert field_name in c, f"{c.get('id')} missing '{field_name}'"

    def test_tool_policy_values_are_valid(self):
        valid = {"required", "optional", "forbidden"}
        for c in EVAL_CASES:
            policy = c.get("tool_policy", "required")
            assert policy in valid, f"{c['id']} has bad tool_policy '{policy}'"

    def test_required_policy_cases_name_their_tools(self):
        for c in EVAL_CASES:
            if c.get("tool_policy", "required") == "required":
                assert c["expected_tools"], (
                    f"{c['id']} is policy=required but names no expected tools"
                )

    def test_forbidden_policy_cases_expect_no_tools(self):
        for c in EVAL_CASES:
            if c.get("tool_policy") == "forbidden":
                assert not c["expected_tools"], (
                    f"{c['id']} is policy=forbidden but lists expected tools"
                )
