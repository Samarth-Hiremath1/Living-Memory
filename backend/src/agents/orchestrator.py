"""
Orchestrator — LangGraph multi-agent pipeline.

Graph structure:

    START
      │
      ▼
  load_context          ← validates guest + stay, loads objects into state
      │
   ───┼──────────────────────
   │                │       │
   ▼                ▼       ▼
flight_node   history_node  wellness_node    ← run in PARALLEL
   │                │       │
   └────────┬───────┘───────┘
            │  (fan-in: place_node waits for all three)
            ▼
        place_node           ← PlaceMaker matching (needs history output)
            │
            ▼
      synthesize_node        ← Claude Sonnet composes the full arrival plan
            │
           END

Benefits of LangGraph over a plain sequential chain:
  • flight, history, and wellness agents run concurrently — reducing wall time
  • Typed state (ArrivalPipelineState) makes data flow explicit and inspectable
  • Conditional edges can reroute based on consent level, available data, etc.
  • Each node is independently testable and swappable
  • The graph can be visualised/exported: pipeline.get_graph().draw_mermaid()
"""

from __future__ import annotations
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END, START

from ..graph.store import graph
from .flight_agent import run_flight_agent
from .history_agent import run_history_agent
from .place_agent import run_place_agent
from .wellness_agent import get_wellness_signals
from .synthesizer import run_synthesizer


# ── Shared state schema ───────────────────────────────────────────────────────

class ArrivalPipelineState(TypedDict):
    """
    State object threaded through every node in the pipeline.
    Each node returns a partial dict; LangGraph merges updates into this state.
    """
    # Inputs
    guest_id: str
    stay_id: str
    welcome_transcript: str | None

    # Loaded context (set by load_context node)
    guest: Any
    stay: Any
    error: str | None

    # Parallel agent outputs (set independently by flight/history/wellness nodes)
    flight_result: dict
    history: dict
    wellness: dict

    # Sequential agent output — depends on history (set by place_node)
    place_result: dict

    # Final output (set by synthesize_node)
    plan: dict | None


# ── Node 1: Load context ──────────────────────────────────────────────────────

def load_context(state: ArrivalPipelineState) -> dict:
    """
    Load Guest and Stay objects from the graph store.
    Sets error if either is missing — all downstream nodes check and no-op.
    """
    guest = graph.get_guest(state["guest_id"])
    stay = graph.get_stay(state["stay_id"])

    if not guest or not stay:
        return {
            "guest": None,
            "stay": None,
            "error": (
                f"Guest or stay not found "
                f"(guest_id={state['guest_id']}, stay_id={state['stay_id']})"
            ),
        }
    return {"guest": guest, "stay": stay, "error": None}


# ── Nodes 2a / 2b / 2c: Run in parallel after load_context ───────────────────

def flight_node(state: ArrivalPipelineState) -> dict:
    """
    Pull live flight data via AviationStack and compute jet lag profile.
    Falls back to an empty dict if flight_number is absent or API is unconfigured.
    """
    if state.get("error") or not state.get("guest"):
        return {"flight_result": {}}
    result = run_flight_agent(state["stay"], state["guest"])
    return {"flight_result": result.to_dict()}


def history_node(state: ArrivalPipelineState) -> dict:
    """
    Analyse all past observations for this guest across every property.
    Claude Haiku extracts patterns, occasions, sensitivities, and standout moments.
    """
    if state.get("error") or not state.get("guest"):
        return {"history": {
            "patterns": [],
            "occasions": [],
            "interests": [],
            "sensitivities": [],
            "cross_property_signals": [],
            "standout_moment": None,
        }}
    return {"history": run_history_agent(state["guest"])}


def wellness_node(state: ArrivalPipelineState) -> dict:
    """
    Read opt-in wellness signals (mock wearable data in this demo).
    Returns surface-level staff notes only — never clinical data.
    """
    if state.get("error") or not state.get("guest"):
        return {"wellness": {"available": False, "staff_note": None}}
    return {"wellness": get_wellness_signals(state["guest"], state["stay"])}


# ── Node 3: PlaceMaker matching (sequential — depends on history output) ──────

def place_node(state: ArrivalPipelineState) -> dict:
    """
    Match guest interests and patterns to the right PlaceMaker at this property.
    Uses history_node output — runs after the parallel fan-in completes.
    """
    if state.get("error") or not state.get("guest"):
        return {"place_result": {}}
    return {
        "place_result": run_place_agent(
            state["guest"],
            state["stay"].property_id,
            state.get("history", {}),
        )
    }


# ── Node 4: Synthesizer ───────────────────────────────────────────────────────

def synthesize_node(state: ArrivalPipelineState) -> dict:
    """
    Combine all agent outputs into a full arrival plan.
    Claude Sonnet writes the dossier; it's then passed through the Friend Filter.
    """
    if state.get("error"):
        return {"plan": {"error": state["error"]}}

    plan = run_synthesizer(
        guest=state["guest"],
        stay=state["stay"],
        flight_result=state.get("flight_result", {}),
        history=state.get("history", {}),
        place_result=state.get("place_result", {}),
        wellness=state.get("wellness", {}),
        welcome_transcript=state.get("welcome_transcript"),
    )
    return {"plan": plan.model_dump()}


# ── Build and compile the graph ───────────────────────────────────────────────

def _build_pipeline() -> Any:
    builder = StateGraph(ArrivalPipelineState)

    # Register nodes
    builder.add_node("load_context", load_context)
    builder.add_node("flight_node", flight_node)
    builder.add_node("history_node", history_node)
    builder.add_node("wellness_node", wellness_node)
    builder.add_node("place_node", place_node)
    builder.add_node("synthesize_node", synthesize_node)

    # Entry point
    builder.add_edge(START, "load_context")

    # Fan-out: after context loads, three agents run in parallel
    builder.add_edge("load_context", "flight_node")
    builder.add_edge("load_context", "history_node")
    builder.add_edge("load_context", "wellness_node")

    # Fan-in: place_node waits for ALL three parallel nodes to complete
    builder.add_edge("flight_node", "place_node")
    builder.add_edge("history_node", "place_node")
    builder.add_edge("wellness_node", "place_node")

    # Sequential tail
    builder.add_edge("place_node", "synthesize_node")
    builder.add_edge("synthesize_node", END)

    return builder.compile()


# Compiled once at import time — reused for every request
_pipeline = _build_pipeline()


# ── Public API ────────────────────────────────────────────────────────────────

def generate_arrival_plan(
    guest_id: str,
    stay_id: str,
    welcome_transcript: str | None = None,
) -> dict:
    """
    Run the LangGraph arrival plan pipeline.
    Returns the ArrivalPlan as a dict, or {"error": "..."} on failure.
    The public signature is unchanged — api.py needs no update.
    """
    initial_state: ArrivalPipelineState = {
        "guest_id": guest_id,
        "stay_id": stay_id,
        "welcome_transcript": welcome_transcript,
        "guest": None,
        "stay": None,
        "error": None,
        "flight_result": {},
        "history": {},
        "wellness": {},
        "place_result": {},
        "plan": None,
    }

    final_state = _pipeline.invoke(initial_state)

    plan = final_state.get("plan")
    if plan is None:
        error = final_state.get("error", "Pipeline did not produce a plan.")
        return {"error": error}

    # If synthesize_node put an error inside the plan dict
    if isinstance(plan, dict) and "error" in plan and len(plan) == 1:
        return plan

    return plan
