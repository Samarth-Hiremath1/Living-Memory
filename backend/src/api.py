"""FastAPI application — all routes for Living Memory."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings
from .graph.schema import Guest, Stay, Observation, ObservationSource, ConsentLevel
from .graph.store import graph
from .graph.identity import find_cross_property_duplicates, merge_guest_profiles
from .agents.orchestrator import generate_arrival_plan
from .agents.friend_filter import demo_filter_comparison
from .ingest.flight import get_flight_status
from .ingest.observation import parse_observation
from .voice.ambassador import get_signed_url, get_ambassador_config
from .voice.stt import transcribe_audio
from .voice.briefing_tts import dossier_to_audio

app = FastAPI(title="Living Memory API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Seed data on startup ──────────────────────────────────────────────────────

@app.on_event("startup")
async def seed_data() -> None:
    """Load synthetic data and property data into the graph on startup."""
    data_dir = Path("../data")

    # Load properties
    for prop_file in (data_dir / "properties").glob("*.json"):
        try:
            from .graph.schema import Property
            prop = Property.model_validate(json.loads(prop_file.read_text()))
            graph.upsert_property(prop)
        except Exception:
            pass

    # Load placemakers
    pm_file = data_dir / "placemakers" / "placemakers.json"
    if pm_file.exists():
        try:
            from .graph.schema import PlaceMaker
            pms = json.loads(pm_file.read_text())
            for pm_data in pms:
                pm = PlaceMaker.model_validate(pm_data)
                graph.upsert_placemaker(pm)
        except Exception:
            pass

    # Load synthetic guests
    synthetic_file = data_dir / "synthetic" / "guests.json"
    if synthetic_file.exists():
        try:
            data = json.loads(synthetic_file.read_text())
            graph.bulk_load(data)
        except Exception:
            pass


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "guests": len(graph.list_guests())}


# ── Guests ────────────────────────────────────────────────────────────────────

@app.get("/guests")
async def list_guests() -> list[dict]:
    return [g.model_dump() for g in graph.list_guests()]


@app.get("/guests/{guest_id}")
async def get_guest(guest_id: str) -> dict:
    guest = graph.get_guest(guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest.model_dump()


@app.get("/guests/{guest_id}/stays")
async def get_guest_stays(guest_id: str) -> list[dict]:
    return [s.model_dump() for s in graph.get_stays_for_guest(guest_id)]


@app.get("/guests/{guest_id}/observations")
async def get_guest_observations(guest_id: str) -> list[dict]:
    return [o.model_dump() for o in graph.get_observations_for_guest(guest_id)]


class UpdateConsentRequest(BaseModel):
    consent_level: ConsentLevel


@app.patch("/guests/{guest_id}/consent")
async def update_consent(guest_id: str, body: UpdateConsentRequest) -> dict:
    guest = graph.get_guest(guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    guest.consent_level = body.consent_level
    graph.upsert_guest(guest)
    return {"guest_id": guest_id, "consent_level": guest.consent_level}


@app.delete("/guests/{guest_id}/forget")
async def forget_guest(guest_id: str) -> dict:
    """Forget Me Everywhere — delete all data for this guest."""
    guest = graph.get_guest(guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    with graph._lock:
        # Remove observations
        obs_ids = [o.id for o in graph.get_observations_for_guest(guest_id)]
        for oid in obs_ids:
            del graph._store.observations[oid]
        # Remove stays
        stay_ids = [s.id for s in graph.get_stays_for_guest(guest_id)]
        for sid in stay_ids:
            del graph._store.stays[sid]
        # Remove guest
        del graph._store.guests[guest_id]

    graph.save()
    return {"deleted": True, "guest_id": guest_id}


# ── Stays ─────────────────────────────────────────────────────────────────────

@app.get("/stays/{stay_id}")
async def get_stay(stay_id: str) -> dict:
    stay = graph.get_stay(stay_id)
    if not stay:
        raise HTTPException(status_code=404, detail="Stay not found")
    return stay.model_dump()


# ── Arrivals ──────────────────────────────────────────────────────────────────

class GeneratePlanRequest(BaseModel):
    guest_id: str
    stay_id: str
    welcome_transcript: str | None = None


@app.post("/arrivals/generate-plan")
async def generate_plan(body: GeneratePlanRequest) -> dict:
    """Run the full orchestration pipeline and return the arrival plan."""
    result = generate_arrival_plan(
        guest_id=body.guest_id,
        stay_id=body.stay_id,
        welcome_transcript=body.welcome_transcript,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/arrivals/today")
async def todays_arrivals() -> list[dict]:
    """Return all stays arriving today (for manager dashboard)."""
    from datetime import date
    today = date.today().isoformat()
    stays = [s for s in graph.raw.stays.values() if s.check_in.startswith(today)]

    arrivals = []
    for stay in stays:
        guest = graph.get_guest(stay.guest_id)
        plan = graph.get_arrival_plan_for_stay(stay.id)
        arrivals.append({
            "stay": stay.model_dump(),
            "guest": guest.model_dump() if guest else None,
            "plan": plan.model_dump() if plan else None,
        })
    return arrivals


@app.get("/arrivals/inhouse")
async def inhouse_guests() -> list[dict]:
    """Return all current in-house guests (for concierge view)."""
    from datetime import date
    today = date.today().isoformat()
    stays = [
        s for s in graph.raw.stays.values()
        if s.check_in <= today and (s.check_out is None or s.check_out >= today)
    ]

    result = []
    for stay in stays:
        guest = graph.get_guest(stay.guest_id)
        observations = graph.get_observations_for_stay(stay.id)
        plan = graph.get_arrival_plan_for_stay(stay.id)
        result.append({
            "stay": stay.model_dump(),
            "guest": guest.model_dump() if guest else None,
            "recent_observations": [o.model_dump() for o in observations[-5:]],
            "plan": plan.model_dump() if plan else None,
        })
    return result


@app.get("/arrivals/plan/{stay_id}")
async def get_plan(stay_id: str) -> dict:
    plan = graph.get_arrival_plan_for_stay(stay_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found for this stay")
    return plan.model_dump()


# ── Observations ──────────────────────────────────────────────────────────────

class ObservationRequest(BaseModel):
    raw_text: str
    stay_id: str
    guest_id: str
    property_id: str
    staff_id: str | None = None


@app.post("/observations")
async def add_observation(body: ObservationRequest) -> dict:
    obs, action_items = parse_observation(
        raw_text=body.raw_text,
        stay_id=body.stay_id,
        guest_id=body.guest_id,
        property_id=body.property_id,
        source=ObservationSource.STAFF_TEXT,
        staff_id=body.staff_id,
    )
    return {"observation": obs.model_dump(), "action_items": action_items}


@app.post("/observations/voice")
async def add_voice_observation(
    audio: UploadFile = File(...),
    stay_id: str = "",
    guest_id: str = "",
    property_id: str = "",
    staff_id: str | None = None,
) -> dict:
    audio_bytes = await audio.read()
    transcript = transcribe_audio(audio_bytes, audio.content_type or "audio/webm")

    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe audio")

    obs, action_items = parse_observation(
        raw_text=transcript,
        stay_id=stay_id,
        guest_id=guest_id,
        property_id=property_id,
        source=ObservationSource.STAFF_VOICE,
        staff_id=staff_id,
    )
    return {
        "transcript": transcript,
        "observation": obs.model_dump(),
        "action_items": action_items,
    }


# ── Flight ────────────────────────────────────────────────────────────────────

@app.get("/flights/{flight_number}")
async def get_flight(flight_number: str) -> dict:
    info = get_flight_status(flight_number)
    if not info:
        raise HTTPException(status_code=404, detail="Flight not found")
    return info.__dict__


# ── Voice Ambassador ──────────────────────────────────────────────────────────

@app.get("/voice/ambassador-url")
async def get_ambassador_url(guest_name: str = "Guest", property_name: str = "Rosewood") -> dict:
    url = get_signed_url(guest_name=guest_name, property_name=property_name)
    config = get_ambassador_config()
    return {"signed_url": url, "config": config}


# ── Friend Filter Demo ────────────────────────────────────────────────────────

class FilterRequest(BaseModel):
    raw_insight: str


@app.post("/demo/friend-filter")
async def demo_friend_filter(body: FilterRequest) -> dict:
    """Live demo endpoint: show raw vs. friend-filtered insight."""
    result = demo_filter_comparison(body.raw_insight)
    return result


# ── Properties ────────────────────────────────────────────────────────────────

@app.get("/properties")
async def list_properties() -> list[dict]:
    return [p.model_dump() for p in graph.list_properties()]


@app.get("/properties/{property_id}")
async def get_property(property_id: str) -> dict:
    prop = graph.get_property(property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop.model_dump()


@app.get("/properties/{property_id}/placemakers")
async def get_placemakers(property_id: str) -> list[dict]:
    return [pm.model_dump() for pm in graph.get_placemakers_for_property(property_id)]


# ── Identity resolution ───────────────────────────────────────────────────────

@app.post("/identity/resolve")
async def resolve_identities() -> dict:
    """Find and optionally merge cross-property duplicate guest profiles."""
    duplicates = find_cross_property_duplicates()
    return {
        "duplicates_found": len(duplicates),
        "pairs": [
            {
                "guest_1": d[0].model_dump(),
                "guest_2": d[1].model_dump(),
                "confidence": d[2],
                "reasoning": d[3],
            }
            for d in duplicates
        ],
    }


# ── Briefing audio (optional) ─────────────────────────────────────────────────

@app.get("/arrivals/plan/{stay_id}/audio")
async def get_plan_audio(stay_id: str) -> StreamingResponse:
    plan = graph.get_arrival_plan_for_stay(stay_id)
    if not plan or not plan.raw_dossier:
        raise HTTPException(status_code=404, detail="No dossier found")

    audio = dossier_to_audio(plan.raw_dossier)
    if not audio:
        raise HTTPException(status_code=503, detail="TTS not configured")

    return StreamingResponse(iter([audio]), media_type="audio/mpeg")
