"""
MCP Tool-Use Agent — LangGraph ReAct loop with MCP-style tool definitions.

Architecture:

    START
      │
      ▼
  agent_node  ←──────────────────────┐
  (Claude decides: answer or call     │
   one or more tools)                 │
      │                               │
      ├──(tool_use)──→ tool_node ─────┘   (loop until no more tool calls)
      │
      └──(end_turn / max_steps)──→ END

Each tool follows the MCP tool-definition schema:
  { name, description, input_schema: { type, properties, required } }

Claude reads the full conversation history on every agent_node pass,
so it can chain multiple tool calls and reason across their outputs.
"""

from __future__ import annotations

import json
import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

import anthropic
from langgraph.graph import END, START, StateGraph

from ..config import settings
from ..tools.calculator_tool import calculate
from ..tools.github_tool import search_github
from ..tools.weather_tool import get_weather

# ── MCP-style tool definitions ────────────────────────────────────────────────
# These match the Anthropic tool_use schema (which is itself MCP-compatible).

MCP_TOOLS: list[dict] = [
    {
        "name": "calculator",
        "description": (
            "Evaluate a mathematical expression. Supports arithmetic, percentages, "
            "exponentiation, and common functions (sqrt, log, sin, cos, etc.). "
            "Use this for any calculation rather than doing mental arithmetic. "
            "Examples: '15% of 240', '450 * 4 * 1.085', 'sqrt(144)', '2^10'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "The mathematical expression to evaluate. "
                        "Percentages: '15% of 240'. Powers: '2^10'. "
                        "Functions: 'sqrt(144)', 'log(100)'."
                    ),
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Get the current weather conditions and temperature for any city or location. "
            "Returns temperature in both Celsius and Fahrenheit, humidity, wind speed, "
            "and a short weather description. Use this whenever a user asks about "
            "current weather, temperature, or climate conditions in a place."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": (
                        "City name or location. Examples: 'San Francisco', "
                        "'London', 'Tokyo', 'Menlo Park CA'."
                    ),
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "search_github",
        "description": (
            "Search GitHub for repositories or users. Returns the top matches with "
            "star counts, descriptions, and primary programming language. "
            "Use this to find open-source projects, look up an organisation's repos, "
            "or find GitHub users."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Full-text search query. Be specific for better results. "
                        "Examples: 'anthropic claude python sdk', "
                        "'langchain langgraph examples'."
                    ),
                },
                "search_type": {
                    "type": "string",
                    "enum": ["repositories", "users"],
                    "description": "Whether to search repositories (default) or GitHub users.",
                },
            },
            "required": ["query"],
        },
    },
]

# Map tool name → callable for dispatch
_TOOL_REGISTRY: dict[str, Any] = {
    "calculator": lambda inp: calculate(inp["expression"]),
    "get_weather": lambda inp: get_weather(inp["location"]),
    "search_github": lambda inp: search_github(
        inp["query"], inp.get("search_type", "repositories")
    ),
}

_SYSTEM_PROMPT = """\
You are a research assistant with access to real-time tools. Use them whenever \
a query requires current data or precise calculation — don't estimate or guess.

Guidelines:
- Always call the right tool rather than approximating.
- After receiving tool results, synthesise them into a concise, direct answer.
- If a calculation involves multiple steps, you may call the calculator more than once.
- Keep final answers brief and factual. No need to explain that you used a tool.
"""

_MAX_STEPS = 6  # max tool-call rounds before forcing a final answer

# ── Shared state ──────────────────────────────────────────────────────────────


class MCPAgentState(TypedDict):
    # The original query (never changes)
    query: str
    # Anthropic API message list — grows via operator.add (append-only)
    messages: Annotated[list, operator.add]
    # How many tool-call rounds have completed
    steps: int
    # Set when agent produces a final text response
    final_answer: str | None
    # Set on unrecoverable error
    error: str | None


# ── Return type ───────────────────────────────────────────────────────────────


@dataclass
class MCPAgentResult:
    """Structured result returned by run_mcp_agent()."""

    final_answer: str
    tool_calls: list[dict] = field(default_factory=list)
    steps_taken: int = 0
    error: str | None = None


# ── Nodes ─────────────────────────────────────────────────────────────────────

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def agent_node(state: MCPAgentState) -> dict:
    """
    Call Claude with the current conversation history and the tool definitions.
    If Claude chooses to use a tool, append its response and return.
    If Claude produces a final answer, set final_answer and stop.
    """
    if state.get("steps", 0) >= _MAX_STEPS:
        # Force a finish by asking Claude to summarise without tools
        forced = _client.messages.create(
            model=settings.fast_model,
            max_tokens=512,
            system=_SYSTEM_PROMPT + "\n\nPlease give your best answer now without calling any more tools.",
            messages=state["messages"],
        )
        text = _extract_text(forced.content)
        return {"final_answer": text or "I've reached my reasoning limit.", "messages": []}

    response = _client.messages.create(
        model=settings.fast_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=MCP_TOOLS,
        messages=state["messages"],
    )

    # Convert Anthropic content blocks to plain dicts for JSON-serialisable state
    content_dicts = [_block_to_dict(b) for b in response.content]
    assistant_msg = {"role": "assistant", "content": content_dicts}

    if response.stop_reason == "end_turn":
        # No more tool calls — extract the final text
        text = _extract_text(response.content)
        return {
            "messages": [assistant_msg],
            "final_answer": text or "(no response)",
        }

    # stop_reason == "tool_use" — return the assistant message for tool_node to process
    return {"messages": [assistant_msg]}


def tool_node(state: MCPAgentState) -> dict:
    """
    Find all tool_use blocks in the last assistant message, execute each tool,
    and return a single user message containing all tool_result blocks.
    """
    messages = state["messages"]
    last_assistant = next(
        (m for m in reversed(messages) if m["role"] == "assistant"), None
    )
    if not last_assistant:
        return {"steps": state.get("steps", 0) + 1, "messages": []}

    content = last_assistant.get("content", [])
    tool_use_blocks = [b for b in content if b.get("type") == "tool_use"]

    if not tool_use_blocks:
        return {"steps": state.get("steps", 0) + 1, "messages": []}

    tool_results = []
    for block in tool_use_blocks:
        tool_name = block["name"]
        tool_input = block["input"]
        tool_use_id = block["id"]

        fn = _TOOL_REGISTRY.get(tool_name)
        if fn is None:
            result_text = f"Error: unknown tool '{tool_name}'"
        else:
            try:
                result_text = fn(tool_input)
            except Exception as exc:
                result_text = f"Error executing {tool_name}: {exc}"

        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(result_text),
            }
        )

    tool_result_msg = {"role": "user", "content": tool_results}
    return {
        "steps": state.get("steps", 0) + 1,
        "messages": [tool_result_msg],
    }


# ── Routing ───────────────────────────────────────────────────────────────────


def _route_after_agent(state: MCPAgentState) -> str:
    """Go to tool_node if the last assistant message has tool_use; otherwise END."""
    if state.get("final_answer") is not None:
        return END
    messages = state.get("messages", [])
    last = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
    if last:
        content = last.get("content", [])
        if any(b.get("type") == "tool_use" for b in content):
            return "tool_node"
    return END


# ── Build graph ───────────────────────────────────────────────────────────────


def _build() -> Any:
    builder = StateGraph(MCPAgentState)
    builder.add_node("agent_node", agent_node)
    builder.add_node("tool_node", tool_node)

    builder.add_edge(START, "agent_node")
    builder.add_conditional_edges("agent_node", _route_after_agent)
    builder.add_edge("tool_node", "agent_node")  # always loop back

    return builder.compile()


_pipeline = _build()


# ── Public API ────────────────────────────────────────────────────────────────


def run_mcp_agent(query: str) -> MCPAgentResult:
    """
    Run the MCP tool-use agent on a query and return a structured result.

    The agent will autonomously decide which tools to call (if any),
    execute them, reason over the results, and produce a final answer.
    """
    if not query or not query.strip():
        return MCPAgentResult(final_answer="", error="Query cannot be empty.")

    initial: MCPAgentState = {
        "query": query,
        "messages": [{"role": "user", "content": query}],
        "steps": 0,
        "final_answer": None,
        "error": None,
    }

    try:
        final = _pipeline.invoke(initial)
    except Exception as exc:
        return MCPAgentResult(final_answer="", error=str(exc))

    # Reconstruct which tools were called from the message history
    tool_calls = _extract_tool_calls(final.get("messages", []))

    return MCPAgentResult(
        final_answer=final.get("final_answer") or "",
        tool_calls=tool_calls,
        steps_taken=final.get("steps", 0),
        error=final.get("error"),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _block_to_dict(block: Any) -> dict:
    """Convert an Anthropic SDK content block object to a plain dict."""
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump()
    # Fallback: manually extract known fields
    d: dict = {"type": getattr(block, "type", "unknown")}
    for attr in ("text", "id", "name", "input"):
        val = getattr(block, attr, None)
        if val is not None:
            d[attr] = val
    return d


def _extract_text(content: list) -> str:
    """Pull the text from the first text block in a content list."""
    for block in content:
        b = _block_to_dict(block) if not isinstance(block, dict) else block
        if b.get("type") == "text":
            return b.get("text", "")
    return ""


def _extract_tool_calls(messages: list[dict]) -> list[dict]:
    """Reconstruct a log of {tool, input, output} from the message history."""
    calls = []
    result_map: dict[str, str] = {}

    # First pass: collect tool results by tool_use_id
    for msg in messages:
        if msg.get("role") == "user":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    result_map[block["tool_use_id"]] = block.get("content", "")

    # Second pass: match tool_use blocks with their results
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls.append(
                        {
                            "tool": block["name"],
                            "input": block.get("input", {}),
                            "output": result_map.get(block["id"], "(no result)"),
                        }
                    )
    return calls
