"""Orchestrator — sequential multi-agent pipeline."""

from __future__ import annotations

from ..graph.store import graph
from .flight_agent import run_flight_agent
from .history_agent import run_history_agent
from .place_agent import run_place_agent
from .wellness_agent import get_wellness_signals
from .synthesizer import run_synthesizer


def generate_arrival_plan(
    guest_id: str,
    stay_id: str,
    welcome_transcript: str | None = None,
) -> dict:
    """Run the full orchestration pipeline and return the arrival plan."""
    guest = graph.get_guest(guest_id)
    stay = graph.get_stay(stay_id)

    if not guest or not stay:
        return {"error": f"Guest or stay not found (guest_id={guest_id}, stay_id={stay_id})"}

    # Run agents sequentially
    flight_result = run_flight_agent(stay, guest).to_dict()
    history = run_history_agent(guest)
    place_result = run_place_agent(guest, stay.property_id, history)
    wellness = get_wellness_signals(guest, stay)

    plan = run_synthesizer(
        guest=guest,
        stay=stay,
        flight_result=flight_result,
        history=history,
        place_result=place_result,
        wellness=wellness,
        welcome_transcript=welcome_transcript,
    )

    return plan.model_dump()
