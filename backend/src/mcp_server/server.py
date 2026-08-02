"""
Living Memory MCP server.

A genuine Model Context Protocol server speaking JSON-RPC 2.0 over stdio.
It exposes all three MCP primitives:

  TOOLS      (model-controlled)  — get_weather, get_flight_status, find_placemaker
  RESOURCES  (app-controlled)    — the property's PlaceMaker roster + property profile
  PROMPTS    (user-controlled)   — "brief_me_on_guest", a reusable briefing template

The business logic is NOT reimplemented here. Every tool delegates to the same
functions the rest of the codebase uses (src/tools/*). This module is purely the
protocol layer: schema declaration, dispatch, and content-block marshalling.

Run standalone:
    cd backend && python -m src.mcp_server.server

The server speaks stdio, so running it in a terminal will appear to hang — that
is correct. It is waiting for a JSON-RPC `initialize` on stdin. Use a client
(see src/mcp_server/client.py) or an MCP-compatible host to talk to it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from ..graph.store import graph
from ..tools.flight_status_tool import get_flight_info
from ..tools.placemaker_tool import find_placemaker
from ..tools.weather_tool import get_weather

logger = logging.getLogger("living_memory.mcp_server")

SERVER_NAME = "living-memory"
SERVER_VERSION = "0.1.0"

# The server instance. The decorators below register JSON-RPC method handlers.
server: Server = Server(SERVER_NAME)


# ── TOOLS (model-controlled) ─────────────────────────────────────────────────
#
# Note the key is `inputSchema` (camelCase) — that is the MCP wire spelling.
# The Anthropic messages API uses `input_schema` (snake_case). Translating
# between the two is the client's job, not the server's. See client.py.


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Respond to `tools/list`. Returns the tool catalogue."""
    return [
        types.Tool(
            name="get_weather",
            description=(
                "Get current weather conditions and temperature for any city or "
                "location. Returns temperature in Celsius and Fahrenheit, humidity, "
                "wind speed, and a short description. Useful for arrival planning, "
                "activity recommendations, and what to suggest a guest pack."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "City name or location. Examples: 'Menlo Park', "
                            "'San Francisco', 'Tokyo', 'Napa Valley'."
                        ),
                    }
                },
                "required": ["location"],
            },
        ),
        types.Tool(
            name="get_flight_status",
            description=(
                "Look up live status for an inbound flight by IATA flight number. "
                "Returns airline, route, scheduled vs. estimated arrival, gate and "
                "terminal, delay information, and a jet-lag severity note computed "
                "from the origin timezone. Use whenever a guest's flight is mentioned "
                "or staff need to know when — or how tired — a guest will arrive."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "flight_number": {
                        "type": "string",
                        "description": (
                            "IATA flight number, e.g. 'LH456', 'UA890'. "
                            "Case-insensitive; spaces ignored."
                        ),
                    }
                },
                "required": ["flight_number"],
            },
        ),
        types.Tool(
            name="find_placemaker",
            description=(
                "Search the property's internal roster of PlaceMakers — chefs, "
                "sommeliers, wellness directors, art curators and other in-house "
                "experts — for the best match given a description of a guest's "
                "interests or current state. Returns ranked matches with their "
                "signature offerings. Use to decide who should host an experience "
                "for a guest, not to recommend external venues."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "interests": {
                        "type": "string",
                        "description": (
                            "Free-text description of guest interests or context. "
                            "Examples: 'natural wine and slow afternoons', "
                            "'long-haul arrival, needs to decompress'."
                        ),
                    },
                    "property_id": {
                        "type": "string",
                        "description": (
                            "Property to search. Defaults to 'sand-hill'. "
                            "Other options: 'crillon', 'carlyle', 'hong-kong'."
                        ),
                    },
                },
                "required": ["interests"],
            },
        ),
    ]


# Dispatch table — tool name to a callable taking the arguments dict.
# Mirrors the structure the agent used before, but now lives server-side.
_DISPATCH: dict[str, Any] = {
    "get_weather": lambda a: get_weather(a["location"]),
    "get_flight_status": lambda a: get_flight_info(a["flight_number"]),
    "find_placemaker": lambda a: find_placemaker(
        a["interests"], a.get("property_id", "sand-hill")
    ),
}


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    """
    Respond to `tools/call`. Executes the named tool and returns content blocks.

    Errors are returned as text content rather than raised, so a failing tool
    degrades into something the model can read and reason about instead of
    terminating the session. This mirrors the pre-MCP agent's behaviour and is
    what the `degraded-api` eval slice exercises.
    """
    args = arguments or {}
    logger.info("tools/call name=%s args=%s", name, args)

    fn = _DISPATCH.get(name)
    if fn is None:
        return [types.TextContent(type="text", text=f"Error: unknown tool '{name}'")]

    try:
        result = fn(args)
    except KeyError as exc:
        result = f"Error: missing required argument {exc} for tool '{name}'"
    except Exception as exc:  # noqa: BLE001 - deliberate: surface to the model
        result = f"Error executing {name}: {exc}"

    return [types.TextContent(type="text", text=str(result))]


# ── RESOURCES (application-controlled) ───────────────────────────────────────
#
# Resources are context the *host application* chooses to attach. The model
# does not invoke them. Here the roster is a natural resource: it is reference
# data a client may want to load up-front rather than have the model go
# fishing for via a tool call.

_ROSTER_URI = "livingmemory://sand-hill/placemakers"
_PROPERTY_URI = "livingmemory://sand-hill/profile"


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """Respond to `resources/list`."""
    return [
        types.Resource(
            uri=_ROSTER_URI,
            name="PlaceMaker roster — Rosewood Sand Hill",
            description=(
                "The full in-house expert roster for Sand Hill: names, roles, "
                "bios, signature offerings, and ideal guest profiles."
            ),
            mimeType="application/json",
        ),
        types.Resource(
            uri=_PROPERTY_URI,
            name="Property profile — Rosewood Sand Hill",
            description=(
                "Property character, signature amenities, welcome amenity options "
                "and cultural calendar."
            ),
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: Any) -> str:
    """Respond to `resources/read`. Returns the resource body as a string."""
    uri_str = str(uri)
    logger.info("resources/read uri=%s", uri_str)

    if uri_str == _ROSTER_URI:
        placemakers = graph.get_placemakers_for_property("sand-hill")
        payload = [
            {
                "name": pm.name,
                "role": pm.role,
                "location": pm.location,
                "bio": pm.bio,
                "offerings": pm.offerings,
                "ideal_guest_profiles": pm.ideal_guest_profiles,
            }
            for pm in placemakers
        ]
        return json.dumps(payload, indent=2)

    if uri_str == _PROPERTY_URI:
        prop = graph.get_property("sand-hill")
        if prop is None:
            return json.dumps({"error": "property 'sand-hill' not loaded"})
        return json.dumps(
            {
                "name": prop.name,
                "city": prop.city,
                "country": prop.country,
                "character": prop.character,
                "signature_amenities": prop.signature_amenities,
                "welcome_amenity_options": prop.welcome_amenity_options,
                "cultural_calendar": prop.cultural_calendar,
            },
            indent=2,
        )

    raise ValueError(f"Unknown resource URI: {uri_str}")


# ── PROMPTS (user-controlled) ────────────────────────────────────────────────
#
# Prompts are templates the *user* selects — typically surfaced in a host as a
# slash command. The model does not choose them and the app does not auto-attach
# them. They return a message list ready to send to a model.


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """Respond to `prompts/list`."""
    return [
        types.Prompt(
            name="brief_me_on_guest",
            description=(
                "Produce a warm, staff-ready arrival briefing for a guest, using "
                "the property's tools to check their flight and match them to the "
                "right in-house expert."
            ),
            arguments=[
                types.PromptArgument(
                    name="guest_name",
                    description="The guest's name, e.g. 'Anna Lindqvist'.",
                    required=True,
                ),
                types.PromptArgument(
                    name="flight_number",
                    description="Inbound IATA flight number, e.g. 'LH456'.",
                    required=False,
                ),
                types.PromptArgument(
                    name="interests",
                    description=(
                        "What the guest cares about, e.g. 'natural wine, hiking'."
                    ),
                    required=False,
                ),
            ],
        )
    ]


@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """Respond to `prompts/get`. Renders the template into concrete messages."""
    if name != "brief_me_on_guest":
        raise ValueError(f"Unknown prompt: {name}")

    args = arguments or {}
    guest = args.get("guest_name", "the arriving guest")
    flight = args.get("flight_number")
    interests = args.get("interests")

    lines = [
        f"Prepare an arrival briefing for {guest}.",
        "",
        "Use the tools available to you:",
    ]
    if flight:
        lines.append(
            f"- Check flight {flight} for arrival timing and jet-lag severity."
        )
    else:
        lines.append("- If a flight number is known, check its status.")
    if interests:
        lines.append(
            f"- Find the PlaceMaker best suited to a guest interested in: {interests}."
        )
    else:
        lines.append("- Find a PlaceMaker suited to this guest.")
    lines += [
        "",
        "Then write 3-4 sentences a front-of-house manager could read aloud at "
        "handover. Warm and specific — the way a colleague who knows the guest "
        "would say it. No clinical readouts, no percentages, no mention of a system.",
    ]

    return types.GetPromptResult(
        description=f"Arrival briefing template for {guest}",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text="\n".join(lines)),
            )
        ],
    )


# ── Entrypoint ───────────────────────────────────────────────────────────────


async def main() -> None:
    """Run the server over stdio until the client disconnects."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
