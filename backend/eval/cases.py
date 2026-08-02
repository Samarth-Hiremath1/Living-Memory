"""
Shared eval cases for the Concierge Research Agent.

Consumed by BOTH:
  - tests/test_mcp_agent.py   (pytest parametrize, binary assertions)
  - eval/run_eval.py          (rubric LLM-as-judge scoring + report)

One canonical source so the two layers can never disagree about what the eval
set is.

Slice taxonomy
--------------
  single-tool-external  — one external API call (weather, flight)
  single-tool-internal  — one internal graph lookup (placemaker)
  multi-tool            — chains two or more tools
  no-tool               — should answer directly, no tool
  ambiguous-query       — vague intent; agent must infer or ask
  degraded-api          — tool errors or input is bad; tests graceful handling

tool_policy
-----------
Added to fix a real flaw found in an audit: the original schema encoded a
specific ACTION as ground truth ("this tool must be called"), which punishes an
agent for correctly declining to call a tool. Three policies now:

  "required"  — every tool in expected_tools must be called (default)
  "optional"  — tools in acceptable_tools may be called without penalty, and
                not calling them is equally fine. Scored on the OUTCOME.
  "forbidden" — no tool should be called; calling one is a penalty

This is the difference between grading how the agent got there and grading
whether it worked.
"""

from __future__ import annotations


EVAL_CASES: list[dict] = [
    # ══ single-tool-external (6) ═════════════════════════════════════════════
    {
        "id": "weather_arrival_planning",
        "slice": "single-tool-external",
        "description": "Weather for arrival planning",
        "query": "What's the weather like in Menlo Park right now? A guest is arriving this afternoon.",
        "expected_tools": ["get_weather"],
        "tool_policy": "required",
        "expected_keywords": ["°"],
    },
    {
        "id": "flight_status_basic",
        "slice": "single-tool-external",
        "description": "Inbound flight lookup",
        "query": "Can you check the status of flight LH456? A guest is on it.",
        "expected_tools": ["get_flight_status"],
        "tool_policy": "required",
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
        "tool_policy": "required",
        "expected_keywords": [["jet lag", "long-haul", "fatigue", "tired", "moderate"]],
    },
    # NEW — probes: does the agent normalise a lowercase flight number rather
    # than passing it through raw or refusing?
    {
        "id": "flight_lowercase_normalisation",
        "slice": "single-tool-external",
        "description": "Flight number given in lowercase must still resolve",
        "query": "quick one - is lh456 landing on time?",
        "expected_tools": ["get_flight_status"],
        "tool_policy": "required",
        "expected_keywords": [["LH456", "Lufthansa", "schedule", "arriv"]],
    },
    # NEW — probes: does the agent extract the *location* from a sentence that
    # buries it, rather than passing the whole sentence as the location arg?
    {
        "id": "weather_location_extraction",
        "slice": "single-tool-external",
        "description": "Location must be extracted from a conversational sentence",
        "query": (
            "One of our couples is driving up to Napa Valley tomorrow morning "
            "for a tasting — should they bring layers?"
        ),
        "expected_tools": ["get_weather"],
        "tool_policy": "required",
        "expected_keywords": [["°", "warm", "cool", "mild", "temperature"]],
    },
    # NEW — probes: does a request for two cities produce two separate calls
    # with correctly split arguments?
    {
        "id": "weather_two_cities",
        "slice": "single-tool-external",
        "description": "Two locations should produce two distinct tool calls",
        "query": "Compare the weather in San Francisco and Menlo Park right now.",
        "expected_tools": ["get_weather"],
        "tool_policy": "required",
        "expected_keywords": [["San Francisco"]],
    },

    # ══ single-tool-internal (4) ═════════════════════════════════════════════
    {
        "id": "placemaker_wine",
        "slice": "single-tool-internal",
        "description": "PlaceMaker search — wine enthusiast",
        "query": (
            "I have a guest arriving who loves Napa wines and small "
            "family estates. Who at the property should host them?"
        ),
        "expected_tools": ["find_placemaker"],
        "tool_policy": "required",
        "expected_keywords": [["David", "Park", "sommelier", "wine", "curator"]],
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
        "tool_policy": "required",
        "expected_keywords": [["Natalie", "Cheng", "wellness", "recovery", "restor"]],
    },
    # NEW — probes: does the agent surface the *offerings* attached to a match,
    # not just the person's name? Tests it reads the whole tool result.
    {
        "id": "placemaker_offering_surfaced",
        "slice": "single-tool-internal",
        "description": "Agent must surface a concrete offering, not just a name",
        "query": (
            "Guest is a serious food person and wants to actually meet the chef. "
            "What can we set up and with whom?"
        ),
        "expected_tools": ["find_placemaker"],
        "tool_policy": "required",
        "expected_keywords": [["Chef's Table", "Madera", "Reylon", "Farm"]],
    },
    # NEW — probes: honest reporting when the roster has no good match, rather
    # than inventing a plausible-sounding expert.
    {
        "id": "placemaker_no_match_honest",
        "slice": "single-tool-internal",
        "description": "No roster match — must not fabricate an expert",
        "query": (
            "Do we have anyone on staff who could take a guest deep-sea "
            "fishing for marlin?"
        ),
        "expected_tools": ["find_placemaker"],
        "tool_policy": "required",
        "expected_keywords": [
            ["no ", "not ", "don't", "does not", "unfortunately", "available"]
        ],
    },

    # ══ multi-tool (4) ═══════════════════════════════════════════════════════
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
        "tool_policy": "required",
        "expected_keywords": [["Reylon", "chef", "Madera"]],
    },
    # NEW — probes: three tools in one turn. Tests the parallel tool_use block
    # handling in tool_node under real load.
    {
        "id": "triple_tool_full_arrival",
        "slice": "multi-tool",
        "description": "All three tools needed for one arrival brief",
        "query": (
            "Full picture for tomorrow please: guest lands on LH456, what's the "
            "weather in Menlo Park, and who should host them — they're into wine."
        ),
        "expected_tools": ["get_flight_status", "get_weather", "find_placemaker"],
        "tool_policy": "required",
        "expected_keywords": [["LH456", "Lufthansa"]],
    },
    # NEW — probes: does the output of tool 1 correctly become the *input* to
    # tool 2? True chaining, not just two independent calls.
    {
        "id": "chained_jetlag_drives_placemaker",
        "slice": "multi-tool",
        "description": "Tool 1 output must inform tool 2 input (real dependency)",
        "query": (
            "Check LH456 and then, based on how rough that arrival is going to "
            "be, pick the right person at the property to look after them."
        ),
        "expected_tools": ["get_flight_status", "find_placemaker"],
        "tool_policy": "required",
        "expected_keywords": [["Natalie", "wellness", "recovery", "rest", "restor"]],
    },
    # NEW — probes: does the agent stop at two tools instead of calling the
    # third just because it exists? Tests over-tooling.
    {
        "id": "multi_tool_restraint",
        "slice": "multi-tool",
        "description": "Should use two tools, not reflexively call all three",
        "query": "Is LH456 on time, and what's the weather where they're landing?",
        "expected_tools": ["get_flight_status", "get_weather"],
        "tool_policy": "required",
        "expected_keywords": [["LH456", "Lufthansa"]],
    },

    # ══ no-tool (3) ══════════════════════════════════════════════════════════
    {
        "id": "no_tool_needed",
        "slice": "no-tool",
        "description": "Agent answers general knowledge directly",
        "query": "What is the capital of France?",
        "expected_tools": [],
        "tool_policy": "forbidden",
        "expected_keywords": [["Paris"]],
    },
    # NEW — probes: trivial arithmetic must not trigger a tool. This is the
    # exact failure that broke the original timezone_math case.
    {
        "id": "no_tool_arithmetic",
        "slice": "no-tool",
        "description": "Trivial mental arithmetic must not trigger a tool call",
        "query": (
            "If a guest checks in at 3pm and dinner is 4 hours later, "
            "what time is dinner?"
        ),
        "expected_tools": [],
        "tool_policy": "forbidden",
        "expected_keywords": [["7", "seven"]],
    },
    # NEW — probes: a question ABOUT the agent's capabilities, which tempts it
    # to call a tool to "find out" instead of answering from its tool list.
    {
        "id": "no_tool_capability_question",
        "slice": "no-tool",
        "description": "Meta question about capabilities — answer, don't probe",
        "query": "What kinds of things can you actually look up for me?",
        "expected_tools": [],
        "tool_policy": "forbidden",
        "expected_keywords": [["weather", "flight", "placemaker", "expert"]],
    },

    # ══ ambiguous-query (3) ══════════════════════════════════════════════════
    # FIXED: this case previously had a code comment saying calling
    # find_placemaker was acceptable while expected_tools was empty, which told
    # the judge to penalise exactly what the comment permitted. Now explicitly
    # "optional" — the agent is graded on whether it responded usefully, not on
    # which path it took.
    {
        "id": "ambiguous_vague_request",
        "slice": "ambiguous-query",
        "description": "Vague request — clarifying or attempting are both valid",
        "query": "I have a guest arriving. What should I prepare?",
        "expected_tools": [],
        "acceptable_tools": ["find_placemaker", "get_weather"],
        "tool_policy": "optional",
        "expected_keywords": [
            ["more", "specific", "tell", "interests", "name", "what", "share", "know"]
        ],
    },
    # NEW — probes: an ambiguous pronoun with no antecedent. Should ask which
    # flight rather than hallucinate one.
    {
        "id": "ambiguous_missing_referent",
        "slice": "ambiguous-query",
        "description": "Missing referent — must ask, not invent a flight number",
        "query": "Is their flight delayed?",
        "expected_tools": [],
        "acceptable_tools": [],
        "tool_policy": "optional",
        "expected_keywords": [
            ["which", "what", "flight number", "who", "don't have", "need"]
        ],
    },
    # NEW — probes: an under-specified request that IS answerable if the agent
    # picks a sensible default rather than stalling.
    {
        "id": "ambiguous_reasonable_default",
        "slice": "ambiguous-query",
        "description": "Under-specified but answerable with a sensible default",
        "query": "Someone who likes art is checking in — any ideas?",
        "expected_tools": [],
        "acceptable_tools": ["find_placemaker"],
        "tool_policy": "optional",
        "expected_keywords": [["art", "curator", "gallery", "collection", "who"]],
    },

    # ══ degraded-api (5) ═════════════════════════════════════════════════════
    # NOTE: policy is "optional" here by deliberate design decision. The audit
    # found that requiring get_weather punished the agent for correctly
    # refusing to call an API on obvious garbage. What actually matters is the
    # OUTCOME: it must not fabricate a forecast. Both "called it and reported
    # the error" and "recognised it as invalid" are acceptable paths.
    {
        "id": "degraded_api_bad_location",
        "slice": "degraded-api",
        "description": "Nonsense location — must not fabricate a forecast",
        "query": "What's the weather in xkqzpwrt12345 right now?",
        "expected_tools": [],
        "acceptable_tools": ["get_weather"],
        "tool_policy": "optional",
        "expected_keywords": [
            ["could not", "couldn't", "error", "not find", "invalid", "unable",
             "no data", "doesn't appear", "not a", "recognise", "recognize"]
        ],
    },
    # NEW — probes: a syntactically valid but nonexistent flight number. Unlike
    # the location case this LOOKS legitimate, so the agent should call the tool.
    {
        "id": "degraded_api_nonexistent_flight",
        "slice": "degraded-api",
        "description": "Plausible but nonexistent flight — should call, then report",
        "query": "Can you check flight ZZ9999 for me?",
        "expected_tools": [],
        "acceptable_tools": ["get_flight_status"],
        "tool_policy": "optional",
        "expected_keywords": [
            ["ZZ9999", "not find", "no flight", "unable", "couldn't", "could not",
             "verify", "check", "unavailable", "demo", "placeholder"]
        ],
    },
    # NEW — probes: empty-string argument handling through the MCP boundary.
    {
        "id": "degraded_api_empty_arg",
        "slice": "degraded-api",
        "description": "Empty/unstated location — must ask rather than call blind",
        "query": "What's the weather there?",
        "expected_tools": [],
        "acceptable_tools": ["get_weather"],
        "tool_policy": "optional",
        "expected_keywords": [["where", "which", "location", "city", "specify"]],
    },
    # NEW — probes: unknown property id. Tests that an internal-tool error is
    # handled as gracefully as an external one.
    {
        "id": "degraded_api_unknown_property",
        "slice": "degraded-api",
        "description": "Unknown property — internal tool error handled gracefully",
        "query": (
            "Who are the PlaceMakers at our Reykjavik property? "
            "Guest is into hiking."
        ),
        "expected_tools": [],
        "acceptable_tools": ["find_placemaker"],
        "tool_policy": "optional",
        "expected_keywords": [
            ["no ", "not ", "don't", "does not", "unable", "sand-hill",
             "couldn't", "could not", "unavailable"]
        ],
    },
    # NEW — probes: does one failing tool poison a multi-tool turn, or does the
    # agent still deliver the half that worked? Partial-failure recovery.
    {
        "id": "degraded_partial_failure_recovery",
        "slice": "degraded-api",
        "description": "One tool fails, one succeeds — must still deliver the good half",
        "query": (
            "Check the weather in qqzzxx99999 and also tell me who should host "
            "a guest who loves wine."
        ),
        "expected_tools": ["find_placemaker"],
        "tool_policy": "required",
        "expected_keywords": [["David", "wine", "Park", "curator"]],
    },
]


# ── Helpers ──────────────────────────────────────────────────────────────────


def get_case(case_id: str) -> dict | None:
    """Return a single case by id, or None."""
    return next((c for c in EVAL_CASES if c["id"] == case_id), None)


def cases_by_slice(slice_tag: str) -> list[dict]:
    """Return all cases tagged with the given slice."""
    return [c for c in EVAL_CASES if c.get("slice") == slice_tag]


def all_slices() -> list[str]:
    """Deduplicated slice tags, in first-appearance order."""
    seen: list[str] = []
    for c in EVAL_CASES:
        s = c.get("slice", "unknown")
        if s not in seen:
            seen.append(s)
    return seen


def slice_counts() -> dict[str, int]:
    """Case count per slice — used to assert no slice is under-populated."""
    counts: dict[str, int] = {}
    for c in EVAL_CASES:
        counts[c.get("slice", "unknown")] = counts.get(c.get("slice", "unknown"), 0) + 1
    return counts


def policy_for(case: dict) -> str:
    """Tool policy for a case, defaulting to 'required'."""
    return case.get("tool_policy", "required")
