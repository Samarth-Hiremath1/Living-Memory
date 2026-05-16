"""LangGraph orchestrator — the top-level multi-agent graph."""

from __future__ import annotations
from typing import TypedDict, Any
from langgraph.graph import StateGraph, END

from ..graph.schema import Guest, Stay
from ..graph.store import graph
from .flight_agent import run_flight_agent
from .history_agent import run_history_agent
from .place_agent import run_place_agent
from .wellness_agent import get_wellness_signals
from .synthesizer import run_synthesizer


class OrchestratorState(TypedDict):
    guest_id: str
    stay_id: str
    guest: Guest | None
    stay: Stay | None
    flight_result: dict
    history: dict
    place_result: dict
    wellness: dict
    welcome_transcript: str | None
    arrival_plan_id: str | None
    error: str | None


def load_guest_stay(state: OrchestratorState) -> OrchestratorState:
    guest = graph.get_guest(state["guest_id"])
    stay = graph.get_stay(state["stay_id"])
    if not guest or not stay:
        return {**state, "error": "Guest or stay not found"}
    return {**state, "guest": guest, "stay": stay}


def run_flight(state: OrchestratorState) -> OrchestratorState:
    if state.get("error") or not state["guest"] or not state["stay"]:
        return state
    result = run_flight_agent(state["stay"], state["guest"])
    return {**state, "flight_result": result.to_dict()}


def run_history(state: OrchestratorState) -> OrchestratorState:
    if state.get("error") or not state["guest"]:
        return state
    history = run_history_agent(state["guest"])
    return {**state, "history": history}


def run_place(state: OrchestratorState) -> OrchestratorState:
    if state.get("error") or not state["guest"] or not state["stay"]:
        return state
    place = run_place_agent(state["guest"], state["stay"].property_id, state["history"])
    return {**state, "place_result": place}


def run_wellness(state: OrchestratorState) -> OrchestratorState:
    if state.get("error") or not state["guest"] or not state["stay"]:
        return state
    wellness = get_wellness_signals(state["guest"], state["stay"])
    return {**state, "wellness": wellness}


def run_synthesis(state: OrchestratorState) -> OrchestratorState:
    if state.get("error") or not state["guest"] or not state["stay"]:
        return state
    plan = run_synthesizer(
        guest=state["guest"],
        stay=state["stay"],
        flight_result=state["flight_result"],
        history=state["history"],
        place_result=state["place_result"],
        wellness=state["wellness"],
        welcome_transcript=state.get("welcome_transcript"),
    )
    return {**state, "arrival_plan_id": plan.id}


def build_orchestrator() -> Any:
    workflow = StateGraph(OrchestratorState)

    workflow.add_node("load", load_guest_stay)
    workflow.add_node("flight", run_flight)
    workflow.add_node("history", run_history)
    workflow.add_node("place", run_place)
    workflow.add_node("wellness", run_wellness)
    workflow.add_node("synthesize", run_synthesis)

    workflow.set_entry_point("load")
    workflow.add_edge("load", "flight")
    workflow.add_edge("load", "history")
    # place and wellness depend on history
    workflow.add_edge("history", "place")
    workflow.add_edge("history", "wellness")
    # synthesizer waits for all
    workflow.add_edge("flight", "synthesize")
    workflow.add_edge("place", "synthesize")
    workflow.add_edge("wellness", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()


# Compiled graph singleton
orchestrator = build_orchestrator()


def generate_arrival_plan(
    guest_id: str,
    stay_id: str,
    welcome_transcript: str | None = None,
) -> dict:
    """Run the full orchestration pipeline and return the arrival plan."""
    initial_state: OrchestratorState = {
        "guest_id": guest_id,
        "stay_id": stay_id,
        "guest": None,
        "stay": None,
        "flight_result": {},
        "history": {},
        "place_result": {},
        "wellness": {},
        "welcome_transcript": welcome_transcript,
        "arrival_plan_id": None,
        "error": None,
    }

    final_state = orchestrator.invoke(initial_state)

    if final_state.get("error"):
        return {"error": final_state["error"]}

    plan_id = final_state.get("arrival_plan_id")
    if plan_id:
        plan = graph.get_arrival_plan_for_stay(stay_id)
        if plan:
            return plan.model_dump()

    return {"error": "Orchestration completed but no plan generated"}
