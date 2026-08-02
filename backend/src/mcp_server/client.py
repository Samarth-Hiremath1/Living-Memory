"""
MCP client bridge.

Connects to the Living Memory MCP server over stdio, performs the initialize
handshake, discovers tools via `tools/list`, and routes execution through
`tools/call`.

Why this is more than a thin wrapper
------------------------------------
The MCP Python SDK is async, and an stdio session must stay open for the life
of the conversation (the server is a subprocess; reconnecting per tool call
would mean re-spawning and re-handshaking every time). The LangGraph nodes in
mcp_agent.py are synchronous.

So this module runs a dedicated event loop on a background daemon thread and
holds the session open there. Synchronous callers submit coroutines to that
loop with `asyncio.run_coroutine_threadsafe` and block on the result. The
session is a process-wide singleton, so the subprocess spawn and handshake are
paid once per process, not once per request.

Schema translation
------------------
MCP declares `inputSchema` (camelCase). The Anthropic messages API expects
`input_schema` (snake_case). Translating between them is the client's job —
the server stays protocol-pure. That translation is `_mcp_tool_to_anthropic`.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("living_memory.mcp_client")

# Launch the server as a module so relative imports inside it resolve.
DEFAULT_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "src.mcp_server.server"],
    env=None,
)

_CALL_TIMEOUT_S = 30.0
_CONNECT_TIMEOUT_S = 30.0


class MCPClientBridge:
    """A persistent MCP stdio session usable from synchronous code."""

    def __init__(self, params: StdioServerParameters | None = None) -> None:
        self._params = params or DEFAULT_SERVER_PARAMS
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: ClientSession | None = None
        self._ready = threading.Event()
        self._shutdown = threading.Event()
        self._start_error: BaseException | None = None
        self._tools_cache: list[dict] | None = None
        self._lock = threading.Lock()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the server subprocess and complete the initialize handshake."""
        with self._lock:
            if self._ready.is_set():
                return
            self._thread = threading.Thread(
                target=self._run_loop, name="mcp-client-loop", daemon=True
            )
            self._thread.start()
            if not self._ready.wait(timeout=_CONNECT_TIMEOUT_S):
                raise RuntimeError("MCP server did not become ready in time")
            if self._start_error is not None:
                raise RuntimeError(
                    f"MCP server failed to start: {self._start_error}"
                ) from self._start_error

    def _run_loop(self) -> None:
        """Background thread: owns the event loop and the open session."""
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._serve())
        except BaseException as exc:  # noqa: BLE001 - reported to start()
            self._start_error = exc
            self._ready.set()
        finally:
            try:
                loop.close()
            except Exception:  # noqa: BLE001
                pass

    async def _serve(self) -> None:
        """Open the stdio session, initialize, then idle until shutdown."""
        async with stdio_client(self._params) as (read, write):
            async with ClientSession(read, write) as session:
                # This is the JSON-RPC `initialize` request + `initialized`
                # notification. Nothing else may be sent before it completes.
                await session.initialize()
                self._session = session
                logger.info("MCP session initialized")
                self._ready.set()
                # Park here so the subprocess and streams stay open.
                while not self._shutdown.is_set():
                    await asyncio.sleep(0.05)

    def stop(self) -> None:
        """Signal the background loop to tear the session down."""
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._ready.clear()
        self._session = None
        self._tools_cache = None

    # ── sync bridge ──────────────────────────────────────────────────────────

    def _submit(self, coro: Any) -> Any:
        if self._loop is None or self._session is None:
            raise RuntimeError("MCP client not started — call start() first")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=_CALL_TIMEOUT_S)

    # ── protocol operations ──────────────────────────────────────────────────

    def list_tools(self, *, refresh: bool = False) -> list[dict]:
        """
        Call `tools/list` and return the catalogue in Anthropic tool format.

        Cached after the first call — the catalogue is static for this server.
        Pass refresh=True to re-query (a real host would instead subscribe to
        `notifications/tools/list_changed`).
        """
        self.start()
        if self._tools_cache is not None and not refresh:
            return self._tools_cache

        assert self._session is not None
        result = self._submit(self._session.list_tools())
        tools = [_mcp_tool_to_anthropic(t) for t in result.tools]
        self._tools_cache = tools
        logger.info("tools/list returned %d tools", len(tools))
        return tools

    def call_tool(self, name: str, arguments: dict) -> str:
        """
        Call `tools/call` and flatten the response content blocks to text.

        Never raises for tool-level failures — transport and protocol errors are
        converted to an error string so the agent loop can feed them back to the
        model as a tool_result, same as a tool that returned an error itself.
        """
        self.start()
        assert self._session is not None
        try:
            result = self._submit(self._session.call_tool(name, arguments))
        except Exception as exc:  # noqa: BLE001
            logger.warning("tools/call transport error name=%s err=%s", name, exc)
            return f"Error calling {name} over MCP: {exc}"

        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else str(block))
        out = "\n".join(parts) if parts else "(empty tool result)"

        if getattr(result, "isError", False):
            return f"Tool reported an error: {out}"
        return out

    def list_resources(self) -> list[dict]:
        """Call `resources/list`."""
        self.start()
        assert self._session is not None
        result = self._submit(self._session.list_resources())
        return [
            {
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description,
                "mimeType": r.mimeType,
            }
            for r in result.resources
        ]

    def read_resource(self, uri: str) -> str:
        """Call `resources/read` and flatten contents to text."""
        self.start()
        assert self._session is not None
        result = self._submit(self._session.read_resource(uri))
        parts = [getattr(c, "text", "") or "" for c in result.contents]
        return "\n".join(p for p in parts if p)

    def list_prompts(self) -> list[dict]:
        """Call `prompts/list`."""
        self.start()
        assert self._session is not None
        result = self._submit(self._session.list_prompts())
        return [
            {
                "name": p.name,
                "description": p.description,
                "arguments": [
                    {
                        "name": a.name,
                        "description": a.description,
                        "required": a.required,
                    }
                    for a in (p.arguments or [])
                ],
            }
            for p in result.prompts
        ]

    def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> str:
        """Call `prompts/get` and return the rendered user message text."""
        self.start()
        assert self._session is not None
        result = self._submit(self._session.get_prompt(name, arguments or {}))
        parts = []
        for m in result.messages:
            text = getattr(m.content, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts)


def _mcp_tool_to_anthropic(tool: Any) -> dict:
    """
    Translate one MCP Tool into the Anthropic messages-API tool shape.

    MCP:       {name, description, inputSchema}
    Anthropic: {name, description, input_schema}

    This is the entire impedance mismatch between the two, which is why MCP
    servers are portable across hosts — each host writes this one function.
    """
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


# Process-wide singleton. Lazily started on first use.
_bridge: MCPClientBridge | None = None
_bridge_lock = threading.Lock()


def get_bridge() -> MCPClientBridge:
    """Return the process-wide MCP client, starting it if necessary."""
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = MCPClientBridge()
    _bridge.start()
    return _bridge


def shutdown_bridge() -> None:
    """Tear down the process-wide client (used by tests and app shutdown)."""
    global _bridge
    with _bridge_lock:
        if _bridge is not None:
            _bridge.stop()
            _bridge = None
