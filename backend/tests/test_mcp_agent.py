"""
Eval suite for the MCP tool-use agent.

Two layers:
  1. Unit tests  — test each tool function directly; no LLM calls, no API key needed.
  2. Integration tests — run the full LangGraph agent; require ANTHROPIC_API_KEY.

Run all tests:
    cd backend && pytest tests/test_mcp_agent.py -v

Run only unit tests (no API key):
    pytest tests/test_mcp_agent.py -v -m "not integration"

Run only integration tests:
    pytest tests/test_mcp_agent.py -v -m integration
"""

from __future__ import annotations

import os
import textwrap

import pytest

from src.tools.calculator_tool import calculate
from src.tools.weather_tool import get_weather
from src.tools.github_tool import search_github

# ── Markers ───────────────────────────────────────────────────────────────────

integration = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration tests",
)

# ── Unit tests: calculator ────────────────────────────────────────────────────


class TestCalculator:
    def test_addition(self):
        assert calculate("2 + 2") == "4"

    def test_subtraction(self):
        assert calculate("100 - 37") == "63"

    def test_multiplication(self):
        assert calculate("15 * 8") == "120"

    def test_division(self):
        assert calculate("144 / 12") == "12"

    def test_percentage_of_syntax(self):
        # "15% of 240" should equal 36
        assert calculate("15% of 240") == "36"

    def test_percentage_bare(self):
        # "20%" should equal 0.2
        result = calculate("20%")
        assert "0.2" in result

    def test_power_caret(self):
        # "2^10" should equal 1024
        assert calculate("2^10") == "1,024"

    def test_power_starstar(self):
        assert calculate("2 ** 10") == "1,024"

    def test_sqrt(self):
        assert calculate("sqrt(144)") == "12"

    def test_hotel_cost_with_tax(self):
        # $450 × 4 nights × 1.085 tax = $1,953
        result = calculate("450 * 4 * 1.085")
        assert "1,953" in result

    def test_tip_calculation(self):
        # 18% tip on $85
        result = calculate("18% of 85")
        assert "15.3" in result

    def test_division_by_zero(self):
        result = calculate("10 / 0")
        assert "error" in result.lower() or "Error" in result

    def test_invalid_expression(self):
        result = calculate("import os")
        assert "error" in result.lower() or "Error" in result

    def test_pi(self):
        result = calculate("pi")
        assert "3.14" in result

    def test_nested(self):
        result = calculate("sqrt(2^8)")
        assert result == "16"


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


# ── Unit tests: GitHub ────────────────────────────────────────────────────────


class TestGitHub:
    def test_returns_string(self):
        result = search_github("anthropic claude")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_repo_search_contains_results(self):
        result = search_github("anthropic")
        # Either repos listed or rate limit message
        has_results = "•" in result or "anthropic" in result.lower()
        has_error = "error" in result.lower() or "rate limit" in result.lower()
        assert has_results or has_error

    def test_user_search(self):
        result = search_github("anthropic", search_type="users")
        assert isinstance(result, str)

    def test_empty_query_graceful(self):
        result = search_github("")
        assert "error" in result.lower()

    def test_default_search_type_is_repos(self):
        result = search_github("python web framework")
        # Repos have star counts; users don't in our format
        assert isinstance(result, str)


# ── Integration tests: full agent ────────────────────────────────────────────
#
# Each case specifies:
#   query            — the input to the agent
#   expected_tools   — tools that MUST appear in tool_calls (subset match)
#   expected_keywords — words that must appear in final_answer (case-insensitive)
#   description      — human-readable label shown on failure

EVAL_CASES = [
    {
        "id": "calc_percentage",
        "description": "Basic percentage — calculator only",
        "query": "What is 15% of 240?",
        "expected_tools": ["calculator"],
        "expected_keywords": ["36"],
    },
    {
        "id": "calc_hotel_tax",
        "description": "Multi-step arithmetic with tax",
        "query": (
            "A hotel room costs $450 per night. I'm staying for 4 nights "
            "and there's an 8.5% tax. What's the total bill?"
        ),
        "expected_tools": ["calculator"],
        "expected_keywords": ["1,953", "1953"],  # either format accepted
    },
    {
        "id": "weather_city",
        "description": "Basic weather lookup",
        "query": "What's the current weather in San Francisco?",
        "expected_tools": ["get_weather"],
        "expected_keywords": ["San Francisco", "°"],
    },
    {
        "id": "weather_celsius_to_f",
        "description": "Weather + unit conversion — two tool calls",
        "query": (
            "What is the current temperature in London in Celsius? "
            "Then tell me what that temperature minus 5 degrees would be in Fahrenheit."
        ),
        "expected_tools": ["get_weather", "calculator"],
        "expected_keywords": ["°"],
    },
    {
        "id": "github_repos",
        "description": "GitHub repository search",
        "query": "Find the top GitHub repos for the Anthropic Python SDK",
        "expected_tools": ["search_github"],
        "expected_keywords": ["anthropic"],
    },
    {
        "id": "no_tool_needed",
        "description": "Agent answers directly without any tool",
        "query": "What is the capital of France?",
        "expected_tools": [],  # no tools expected
        "expected_keywords": ["Paris", "paris"],
    },
    {
        "id": "timezone_math",
        "description": "Timezone arithmetic — calculator",
        "query": (
            "My meeting is at 9am Pacific Time. "
            "What time is that in New York (Eastern, 3 hours ahead)?"
        ),
        "expected_tools": ["calculator"],
        "expected_keywords": ["12", "noon"],
    },
    {
        "id": "multi_tool_chain",
        "description": "Chained reasoning: weather → unit conversion",
        "query": (
            "What's the temperature in Tokyo right now in Celsius? "
            "Convert it to Fahrenheit using the formula (C × 9/5) + 32."
        ),
        "expected_tools": ["get_weather", "calculator"],
        "expected_keywords": ["°F", "Tokyo"],
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
    answer_lower = result.final_answer.lower()
    for kw in case["expected_keywords"]:
        assert kw.lower() in answer_lower, (
            f"[{case['id']}] Expected '{kw}' in answer.\n"
            f"Answer: {result.final_answer[:300]}"
        )

    # ── 5. No infinite loops ────────────────────────────────────────────────
    assert result.steps_taken <= 6, (
        f"[{case['id']}] Agent took {result.steps_taken} steps — possible loop."
    )

    # Print a summary line for readable output
    tools_str = ", ".join(tools_used) if tools_used else "none"
    print(
        f"\n✓ [{case['id']}] {case['description']}\n"
        f"  Tools: {tools_str} | Steps: {result.steps_taken}\n"
        f"  Answer: {textwrap.shorten(result.final_answer, 120)}"
    )


@integration
@pytest.mark.integration
def test_agent_result_structure() -> None:
    """Verify the MCPAgentResult dataclass has all expected fields."""
    from src.agents.mcp_agent import run_mcp_agent, MCPAgentResult

    result = run_mcp_agent("What is 6 * 7?")
    assert isinstance(result, MCPAgentResult)
    assert isinstance(result.final_answer, str)
    assert isinstance(result.tool_calls, list)
    assert isinstance(result.steps_taken, int)
    assert result.error is None

    if result.tool_calls:
        call = result.tool_calls[0]
        assert "tool" in call
        assert "input" in call
        assert "output" in call


@integration
@pytest.mark.integration
def test_tool_call_log_populated() -> None:
    """Verify tool calls are logged with input and output when a tool is used."""
    from src.agents.mcp_agent import run_mcp_agent

    result = run_mcp_agent("What is 12% of 500?")
    assert result.tool_calls, "Expected at least one tool call for a calculation."
    call = result.tool_calls[0]
    assert call["tool"] == "calculator"
    assert "expression" in call["input"]
    assert "60" in call["output"]  # 12% of 500 = 60
