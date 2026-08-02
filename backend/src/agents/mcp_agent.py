"""
MCP Tool-Use Agent — LangGraph ReAct loop driven by a real MCP server.

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

Tool discovery and execution both go over MCP
---------------------------------------------
This agent holds NO hardcoded tool list. On each run it calls `tools/list`
against the Living Memory MCP server (src/mcp_server/server.py, spoken to over
stdio via src/mcp_server/client.py), translates the returned MCP schemas into
the Anthropic tool format, and routes every execution through `tools/call`.

Consequences worth understanding:
  * Adding a tool to the server makes it available here with no change to this
    file. Discovery is dynamic.
  * This agent would work against any MCP server exposing any tools — nothing
    below names get_weather, get_flight_status or find_placemaker.
  * If the server is unreachable the agent degrades to a no-tool assistant
    rather than crashing (see _discover_tools).

Claude reads the full conversation history on every agent_node pass, so it can
chain multiple tool calls and reason across their outputs.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

import anthropic
from langgraph.graph import END, START, StateGraph

from ..config import settings
from ..mcp_server.client import get_bridge
from ..observability import configure_logging, instrument, logger

# ── Tool discovery over MCP ───────────────────────────────────────────────────


def _discover_tools() -> list[dict]:
    """
    Call `tools/list` on the MCP server and return Anthropic-format tools.

    The bridge caches the catalogue per process, so this is a dict lookup after
    the first call rather than a round trip.

    Degradation: if the server cannot be reached we log and return an empty
    list. Claude then answers without tools instead of the request failing —
    a degraded answer beats a 500 for a concierge asking a question mid-shift.
    """
    configure_logging()
    try:
        return get_bridge().list_tools()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "MCP tool discovery failed; running tool-less: %s",
            exc,
            extra={"event": "mcp_discovery_failed"},
        )
        return []


def get_mcp_tools() -> list[dict]:
    """Public accessor for the discovered tool catalogue (used by the API)."""
    return _discover_tools()

_SYSTEM_PROMPT = """\
You are a Rosewood concierge research assistant. You help staff prepare for and \
respond to guest needs by querying real-time external data (weather, flights) and \
the property's internal roster of in-house experts.

Guidelines:
- Reach for a tool whenever the answer depends on live data, a specific flight, or \
  who at the property should host an experience.
- You can chain multiple tools in a single response — for example, check the \
  weather at the destination, then find the right PlaceMaker for the guest's interests.
- After receiving tool results, synthesise them into a concise, warm reply that a \
  staff member could relay directly. No clinical readouts, no mention of "the system".
- If no tool is needed, just answer directly.
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
    # True when the loop was cut off by _MAX_STEPS rather than finishing
    hit_step_cap: bool


# ── Return type ───────────────────────────────────────────────────────────────


@dataclass
class MCPAgentResult:
    """Structured result returned by run_mcp_agent()."""

    final_answer: str
    tool_calls: list[dict] = field(default_factory=list)
    steps_taken: int = 0
    error: str | None = None
    # True when the answer was forced by the step cap. Without this a truncated
    # run and a clean run are indistinguishable to the caller.
    hit_step_cap: bool = False


# ── Nodes ─────────────────────────────────────────────────────────────────────

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


@instrument("mcp_agent", "agent_node")
def agent_node(state: MCPAgentState) -> dict:
    """
    Call Claude with the current conversation history and the tool definitions
    discovered from the MCP server.

    If Claude chooses to use a tool, append its response and return.
    If Claude produces a final answer, set final_answer and stop.
    """
    if state.get("steps", 0) >= _MAX_STEPS:
        # Force a finish. Note there is no `tools=` argument here: with no tools
        # in the request Claude *cannot* emit a tool_use block, so the router
        # cannot reach tool_node. Termination is structural, not persuasion.
        forced = _client.messages.create(
            model=settings.fast_model,
            max_tokens=512,
            system=_SYSTEM_PROMPT + "\n\nPlease give your best answer now without calling any more tools.",
            messages=state["messages"],
        )
        text = _extract_text(forced.content)
        logger.info(
            "agent hit max steps, forcing final answer",
            extra={"event": "max_steps", "steps": state.get("steps", 0)},
        )
        return {
            "final_answer": text or "I've reached my reasoning limit.",
            "messages": [],
            "hit_step_cap": True,
        }

    tools = _discover_tools()
    kwargs: dict[str, Any] = {
        "model": settings.fast_model,
        "max_tokens": 1024,
        "system": _SYSTEM_PROMPT,
        "messages": state["messages"],
    }
    # Passing tools=[] is rejected by the API; omit the key entirely instead.
    if tools:
        kwargs["tools"] = tools

    response = _client.messages.create(**kwargs)

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


@instrument("mcp_agent", "tool_node")
def tool_node(state: MCPAgentState) -> dict:
    """
    Find all tool_use blocks in the last assistant message, execute each one via
    the MCP server's `tools/call`, and return a single user message containing
    all tool_result blocks.

    A response may contain several tool_use blocks (Claude can request tools in
    parallel), so this iterates rather than handling one.
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
    bridge = get_bridge()
    for block in tool_use_blocks:
        tool_name = block["name"]
        tool_input = block["input"]
        tool_use_id = block["id"]

        # Every execution is a JSON-RPC `tools/call` to the MCP server.
        # call_tool never raises — protocol and tool errors both come back as
        # text so the model can read and reason about the failure.
        result_text = bridge.call_tool(tool_name, tool_input)
        logger.info(
            "tool executed via MCP",
            extra={"event": "tool_call", "tool": tool_name},
        )

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
        "hit_step_cap": False,
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
        hit_step_cap=bool(final.get("hit_step_cap", False)),
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
