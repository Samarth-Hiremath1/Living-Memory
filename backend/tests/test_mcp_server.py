"""
Tests for the Living Memory MCP server.

These start a REAL server subprocess over stdio and speak actual JSON-RPC to
it — initialize handshake, tools/list, tools/call, resources/*, prompts/*.
No mocks, no in-process shortcuts. If the protocol layer breaks, these fail.

No ANTHROPIC_API_KEY is required: the MCP layer is model-independent.
"""

from __future__ import annotations

import json

import pytest

from src.mcp_server.client import MCPClientBridge


@pytest.fixture(scope="module")
def bridge():
    """One server subprocess shared across the module; torn down at the end."""
    b = MCPClientBridge()
    b.start()
    yield b
    b.stop()


# ── Handshake + discovery ────────────────────────────────────────────────────


class TestHandshakeAndDiscovery:
    def test_server_starts_and_initializes(self, bridge):
        # start() returning without raising means `initialize` completed and the
        # server replied with its capabilities.
        assert bridge._session is not None

    def test_tools_list_returns_three_tools(self, bridge):
        tools = bridge.list_tools()
        names = {t["name"] for t in tools}
        assert names == {"get_weather", "get_flight_status", "find_placemaker"}

    def test_schema_translated_to_anthropic_format(self, bridge):
        """MCP sends inputSchema; the client must hand back input_schema."""
        tools = bridge.list_tools()
        for t in tools:
            assert "input_schema" in t, "client failed to translate inputSchema"
            assert "inputSchema" not in t, "raw MCP key leaked through"
            assert t["input_schema"]["type"] == "object"
            assert "properties" in t["input_schema"]

    def test_tools_have_descriptions(self, bridge):
        # Descriptions drive model tool selection — empty ones are a real bug.
        for t in bridge.list_tools():
            assert len(t["description"]) > 40

    def test_required_fields_declared(self, bridge):
        by_name = {t["name"]: t for t in bridge.list_tools()}
        assert by_name["get_weather"]["input_schema"]["required"] == ["location"]
        assert by_name["get_flight_status"]["input_schema"]["required"] == [
            "flight_number"
        ]
        assert by_name["find_placemaker"]["input_schema"]["required"] == ["interests"]


# ── tools/call ───────────────────────────────────────────────────────────────


class TestCallTool:
    def test_call_find_placemaker_returns_real_result(self, bridge):
        out = bridge.call_tool("find_placemaker", {"interests": "Napa wine"})
        assert isinstance(out, str)
        assert len(out) > 20
        assert "PlaceMakers at sand-hill" in out

    def test_call_flight_status(self, bridge):
        out = bridge.call_tool("get_flight_status", {"flight_number": "LH456"})
        assert "LH456" in out
        assert "FRA" in out or "Frankfurt" in out

    def test_optional_argument_defaults_server_side(self, bridge):
        """property_id is optional; the server must apply the default."""
        out = bridge.call_tool("find_placemaker", {"interests": "wine"})
        assert "sand-hill" in out

    def test_unknown_tool_returns_error_text_not_exception(self, bridge):
        out = bridge.call_tool("no_such_tool", {})
        assert "error" in out.lower()

    def test_missing_required_arg_is_handled(self, bridge):
        """A malformed call must degrade to readable text, not kill the session."""
        out = bridge.call_tool("get_weather", {})
        assert "error" in out.lower()

    def test_session_survives_a_bad_call(self, bridge):
        """The critical property: one bad call must not poison the session."""
        bridge.call_tool("no_such_tool", {})
        out = bridge.call_tool("find_placemaker", {"interests": "wine"})
        assert "PlaceMakers" in out


# ── resources/* ──────────────────────────────────────────────────────────────


class TestResources:
    def test_resources_list(self, bridge):
        uris = {r["uri"] for r in bridge.list_resources()}
        assert "livingmemory://sand-hill/placemakers" in uris
        assert "livingmemory://sand-hill/profile" in uris

    def test_read_roster_resource_is_valid_json(self, bridge):
        body = bridge.read_resource("livingmemory://sand-hill/placemakers")
        data = json.loads(body)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0] and "role" in data[0]

    def test_read_property_resource(self, bridge):
        body = bridge.read_resource("livingmemory://sand-hill/profile")
        data = json.loads(body)
        assert data.get("name")


# ── prompts/* ────────────────────────────────────────────────────────────────


class TestPrompts:
    def test_prompts_list(self, bridge):
        prompts = bridge.list_prompts()
        assert any(p["name"] == "brief_me_on_guest" for p in prompts)

    def test_prompt_declares_arguments(self, bridge):
        p = next(p for p in bridge.list_prompts() if p["name"] == "brief_me_on_guest")
        args = {a["name"]: a for a in p["arguments"]}
        assert args["guest_name"]["required"] is True
        assert args["flight_number"]["required"] is False

    def test_get_prompt_renders_arguments(self, bridge):
        text = bridge.get_prompt(
            "brief_me_on_guest",
            {
                "guest_name": "Anna Lindqvist",
                "flight_number": "LH456",
                "interests": "natural wine",
            },
        )
        assert "Anna Lindqvist" in text
        assert "LH456" in text
        assert "natural wine" in text

    def test_get_prompt_handles_optional_args(self, bridge):
        text = bridge.get_prompt("brief_me_on_guest", {"guest_name": "Marcus Chen"})
        assert "Marcus Chen" in text
        assert len(text) > 100
