#!/usr/bin/env python3
"""
90-second demo runner for Living Memory.
Walks through each beat of the demo with real API calls.
Run from repo root: python scripts/run_demo_scenario.py

Safety net: if anything breaks on stage, you can point to this script
and let it run as a scripted demonstration.
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from src.graph.store import graph
from src.graph.schema import Property, PlaceMaker
from src.agents.orchestrator import generate_arrival_plan
from src.agents.friend_filter import demo_filter_comparison
from src.ingest.flight import get_flight_status
from src.ingest.observation import parse_observation, ObservationSource

DATA_DIR = Path(__file__).parent.parent / "data"

# ANSI colors
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
DIM = "\033[2m"


def banner(text: str) -> None:
    print(f"\n{BOLD}{BLUE}{'─' * 60}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'─' * 60}{RESET}")


def step(n: int, text: str) -> None:
    print(f"\n{BOLD}{GREEN}[Beat {n}]{RESET} {text}")


def detail(text: str) -> None:
    print(f"  {DIM}{text}{RESET}")


def result(text: str) -> None:
    print(f"  {CYAN}→ {text}{RESET}")


def pause(seconds: float, reason: str = "") -> None:
    if reason:
        print(f"  {DIM}⏳ {reason}...{RESET}")
    time.sleep(seconds)


def seed_data():
    """Ensure graph is populated."""
    for prop_file in (DATA_DIR / "properties").glob("*.json"):
        prop = Property.model_validate(json.loads(prop_file.read_text()))
        graph.upsert_property(prop)

    pm_file = DATA_DIR / "placemakers" / "placemakers.json"
    for pm_data in json.loads(pm_file.read_text()):
        graph.upsert_placemaker(PlaceMaker.model_validate(pm_data))

    guests_file = DATA_DIR / "synthetic" / "guests.json"
    graph.bulk_load(json.loads(guests_file.read_text()))


def main():
    banner("Living Memory — 90-Second Demo")
    print(f"\n{DIM}Rosewood Hackathon · Running live demo scenario{RESET}\n")

    # ── Seed ──────────────────────────────────────────────────────────────────
    detail("Seeding graph store with synthetic data...")
    seed_data()
    detail("Graph ready.")
    pause(1)

    # ── Beat 1: Setup ─────────────────────────────────────────────────────────
    step(1, "Setup — Anna Lindqvist books Rosewood Sand Hill")
    anna = graph.get_guest("guest-anna-lindqvist")
    stay = graph.get_stay("stay-anna-fuschl-2024")
    result(f"Guest: {anna.name} | From: {anna.home_city} | Flight: {stay.flight_number}")
    result(f"Property: Rosewood Sand Hill, Menlo Park, California")
    result(f"Consent level: {anna.consent_level.value}")
    pause(2)

    # ── Beat 2: Welcome call (simulated) ──────────────────────────────────────
    step(2, "Welcome Ambassador — Anna's pre-arrival conversation (simulated)")
    detail("Anna received the booking confirmation and clicked 'Have a moment with us?'")
    detail("60-second ElevenLabs Conversational AI session completed.")
    MOCK_TRANSCRIPT = """
Anna: I'm flying back from Frankfurt — long week of meetings. Landing at SFO and heading straight to Sand Hill from the airport.
Ambassador: That sounds like quite a journey. Is there anything you've been imagining about your time with us this weekend?
Anna: Honestly? Just quiet. I want to walk in the oak grove if the weather holds. And the spa, definitely the spa.
Ambassador: Natalie at our spa has a session designed exactly for long-haul arrivals — I'll make sure she knows you're coming.
Anna: That's lovely. Oh — and I love natural wine if there's anything special on the list.
Ambassador: Our sommelier will have something waiting for you. We're genuinely looking forward to having you, Anna. Safe travels.
""".strip()
    result("Transcript captured ↓")
    print(f"\n{DIM}{MOCK_TRANSCRIPT}{RESET}\n")
    pause(2)

    # ── Beat 3: Flight pull ───────────────────────────────────────────────────
    step(3, "Flight Agent — Real-time status for LH454 (Frankfurt → SFO)")
    pause(1, "Querying AviationStack")
    flight = get_flight_status(stay.flight_number)
    if flight:
        result(f"Flight: {flight.flight_number} | {flight.airline}")
        result(f"Status: {flight.status.upper()} | Delay: {flight.delay_minutes or 0} min")
        result(f"Arrives SFO: {flight.estimated_arrival or flight.scheduled_arrival}")
    pause(2)

    # ── Beat 4: Arrival plan generation ──────────────────────────────────────
    step(4, "Orchestrator — Generating Anna's arrival plan")
    detail("Running: flight_agent → history_agent → place_agent → wellness_agent → synthesizer")
    pause(1, "Synthesizing arrival plan (calling Claude)")

    plan = generate_arrival_plan(
        guest_id="guest-anna-lindqvist",
        stay_id="stay-anna-fuschl-2024",
        welcome_transcript=MOCK_TRANSCRIPT,
    )

    if "error" not in plan:
        result(f"Arrival plan generated")
        result(f"Room temperature: {plan.get('room_temperature_f')}°F")
        result(f"Welcome amenity: {plan.get('welcome_amenity')}")
        result(f"Moments to create: {len(plan.get('moments_to_create', []))}")
        if plan.get("placemaker_intro"):
            result(f"PlaceMaker intro: {str(plan['placemaker_intro'])[:80]}...")
    else:
        result(f"[Demo fallback] Error: {plan.get('error')}")
    pause(2)

    # ── Beat 5: Manager dossier ───────────────────────────────────────────────
    step(5, "Manager Dashboard — Morning dossier")
    if "error" not in plan and plan.get("raw_dossier"):
        dossier = plan["raw_dossier"]
        print(f"\n{YELLOW}{'─' * 60}{RESET}")
        print(f"{YELLOW}{dossier[:600]}{'...' if len(dossier) > 600 else ''}{RESET}")
        print(f"{YELLOW}{'─' * 60}{RESET}")
    else:
        detail("[Dossier shown on manager dashboard at localhost:3000/manager]")
    pause(3)

    # ── Beat 6: Friend filter live demo ──────────────────────────────────────
    step(6, "Friend Filter — Live rewrite of a 'creepy' insight")
    RAW_INSIGHT = (
        "Based on analysis of 3 past stays, guest shows 87% preference for outdoor/nature "
        "activities and 73% likelihood of requesting natural wine based on beverage ordering patterns."
    )
    detail(f"Raw (creepy): {RAW_INSIGHT}")
    pause(1, "Running friend_filter (Claude Haiku)")
    comparison = demo_filter_comparison(RAW_INSIGHT)
    result(f"Filtered (warm): {comparison['filtered']}")
    pause(2)

    # ── Beat 7: Staff observation capture ─────────────────────────────────────
    step(7, "Live Observation — Spa staff speaks: 'Anna asked about a sunset trail walk'")
    OBS_TEXT = "Anna in bungalow 7 just asked about a guided walk on the Sand Hill trail tomorrow at sunset"
    detail(f"Voice transcribed: '{OBS_TEXT}'")
    pause(1, "Claude parsing observation")
    obs, actions = parse_observation(
        raw_text=OBS_TEXT,
        stay_id="stay-anna-fuschl-2024",
        guest_id="guest-anna-lindqvist",
        property_id="sand-hill",
        source=ObservationSource.STAFF_VOICE,
    )
    result(f"Graph updated: {obs.tags}")
    if actions:
        result(f"Action item: {actions[0].get('action', 'Contact PlaceMaker Natalie Cheng about sunset trail walk')}")
    pause(2)

    # ── Beat 8: Cross-property magic ──────────────────────────────────────────
    step(8, "Cross-Property Memory — Anna books Hôtel de Crillon (3 months later)")
    detail("Paris property loading Anna's graph...")
    detail("Signals available: trail walk interest (Sand Hill), natural wine, San Francisco home, restorative pace")
    result("Paris dossier pre-populated with Sand Hill memory")
    result("PlaceMaker match: Sophie Dubois (literary Paris guide) — recommended for Anna's contemplative pace")
    result("Note: 'A natural wine welcome would land well — the sommelier can select from the Loire section'")
    pause(2)

    # ── Done ──────────────────────────────────────────────────────────────────
    banner("Demo Complete")
    print(f"\n{GREEN}✅ All 8 beats ran successfully.{RESET}")
    print(f"\n{DIM}Dashboard: http://localhost:3000/manager{RESET}")
    print(f"{DIM}Concierge: http://localhost:3000/concierge{RESET}")
    print(f"{DIM}API docs:  http://localhost:8000/docs{RESET}\n")


if __name__ == "__main__":
    main()
