"""FastAPI application — all routes for Living Memory."""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
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
from .voice.ambassador import get_signed_url, get_ambassador_config, get_concierge_config, CONCIERGE_SYSTEM_PROMPT
from .voice.stt import transcribe_audio
from .voice.briefing_tts import dossier_to_audio
from .agents.welcome_summarizer import summarize_welcome_transcript, extract_preferences_from_transcript

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
    """Forget Me Everywhere — delete all data for this guest across all properties."""
    guest = graph.get_guest(guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    with graph._lock:
        obs_ids = [o.id for o in graph.get_observations_for_guest(guest_id)]
        for oid in obs_ids:
            graph._store.observations.pop(oid, None)
        stay_ids = [s.id for s in graph.get_stays_for_guest(guest_id)]
        for sid in stay_ids:
            graph._store.stays.pop(sid, None)
        graph._store.guests.pop(guest_id, None)

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
    try:
        result = generate_arrival_plan(
            guest_id=body.guest_id,
            stay_id=body.stay_id,
            welcome_transcript=body.welcome_transcript,
        )
        if "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
        if s.property_id == "sand-hill"
        and s.check_in <= today
        and (s.check_out is None or s.check_out >= today)
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
async def add_observation_endpoint(body: ObservationRequest) -> dict:
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
    stay_id: str = Form(""),
    guest_id: str = Form(""),
    property_id: str = Form(""),
    staff_id: str | None = Form(None),
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
        "note": "Demo mode — STT using mock transcription" if not settings.elevenlabs_api_key else None,
    }


# ── Flight ────────────────────────────────────────────────────────────────────

@app.get("/flights/{flight_number}")
async def get_flight(flight_number: str) -> dict:
    info = get_flight_status(flight_number)
    if not info:
        raise HTTPException(status_code=404, detail="Flight not found")
    return info.__dict__


# ── Voice — Welcome Ambassador (Agent 1) ──────────────────────────────────────

@app.get("/voice/ambassador-url")
async def get_ambassador_url(guest_name: str = "Guest", property_name: str = "Rosewood Sand Hill") -> dict:
    """Get a signed URL for the pre-arrival Welcome Ambassador conversation."""
    url = get_signed_url(
        guest_name=guest_name,
        property_name=property_name,
        agent_id=settings.elevenlabs_agent_id,
    )
    config = get_ambassador_config()
    return {"signed_url": url, "config": config}


class WelcomeProcessRequest(BaseModel):
    transcript: str
    guest_id: str
    stay_id: str


@app.post("/voice/process-welcome-call")
async def process_welcome_call(body: WelcomeProcessRequest) -> dict:
    """
    Process the welcome conversation transcript:
    1. Extract a warm summary for the guest UI
    2. Extract structured preferences
    3. Save preferences to the guest's profile
    4. Save an observation so agents and staff see it
    """
    summary_bullets = summarize_welcome_transcript(body.transcript)
    preferences = extract_preferences_from_transcript(body.transcript)

    guest = graph.get_guest(body.guest_id)
    stay = graph.get_stay(body.stay_id)

    if guest and preferences:
        # Merge preferences — lists union, scalars overwrite
        for key, value in preferences.items():
            if key == "notes":
                continue  # handled below
            if isinstance(value, list) and key in guest.preferences and isinstance(guest.preferences.get(key), list):
                merged = list(set((guest.preferences[key] or []) + value))
                guest.preferences[key] = merged
            elif value is not None and value != "null":
                guest.preferences[key] = value
        guest.updated_at = datetime.utcnow()
        graph.upsert_guest(guest)

    if stay and guest:
        # Record as an observation so manager dashboard and concierge see it
        note_text = preferences.get("notes") or "Welcome conversation completed."
        tags = ["welcome_call"]
        if preferences.get("arrival_mood"):
            tags.append(preferences["arrival_mood"])
        if preferences.get("placemaker_match"):
            tags.append("placemaker_suggested")

        obs = Observation(
            stay_id=stay.id,
            guest_id=guest.id,
            property_id=stay.property_id,
            raw_text=note_text,
            tags=tags,
            source=ObservationSource.WELCOME_CALL,
            sentiment="positive",
        )
        graph.add_observation(obs)

    graph.save()
    return {
        "summary": summary_bullets,
        "preferences_saved": bool(preferences),
        "guest_updated": bool(guest and preferences),
    }


# ── Voice — In-Stay Concierge (Agent 2) ──────────────────────────────────────

@app.get("/voice/concierge-url")
async def get_concierge_url(guest_name: str = "Guest", property_name: str = "Rosewood Sand Hill") -> dict:
    """Get a signed URL for the in-stay PlaceMaker Engine concierge agent."""
    url = get_signed_url(
        guest_name=guest_name,
        property_name=property_name,
        agent_id=settings.elevenlabs_assistant_agent_id,
        system_prompt=CONCIERGE_SYSTEM_PROMPT,
    )
    config = get_concierge_config()
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


# ── ElevenLabs Webhook ────────────────────────────────────────────────────────
#
# How to configure in ElevenLabs:
#   1. Go to your Agent settings in the ElevenLabs dashboard
#   2. Navigate to "Webhook" or "Post-call webhook" section
#   3. Set the URL to: https://your-domain.com/voice/elevenlabs-webhook
#   4. ElevenLabs will POST a JSON payload when each conversation ends
#   5. Make sure your domain is publicly accessible (use ngrok for local dev)

class ElevenLabsTranscriptLine(BaseModel):
    role: str
    message: str


class ElevenLabsWebhookMetadata(BaseModel):
    stay_id: str | None = None
    guest_id: str | None = None


class ElevenLabsWebhookPayload(BaseModel):
    conversation_id: str | None = None
    agent_id: str | None = None
    status: str | None = None
    transcript: list[ElevenLabsTranscriptLine] = []
    metadata: dict[str, Any] | None = None


async def _process_elevenlabs_webhook(payload: ElevenLabsWebhookPayload) -> None:
    """Background task: extract transcript and process as a welcome call."""
    meta = payload.metadata or {}
    stay_id = meta.get("stay_id", "")
    guest_id = meta.get("guest_id", "")

    if not stay_id or not guest_id:
        return  # No guest context — skip

    # Format transcript as readable string
    raw_lines = []
    for line in payload.transcript:
        speaker = "Ambassador" if line.role in ("agent", "ai", "assistant") else "Guest"
        raw_lines.append(f"{speaker}: {line.message}")
    raw_transcript = "\n".join(raw_lines)

    if not raw_transcript.strip():
        return

    # Reuse the process-welcome-call logic
    req = WelcomeProcessRequest(
        transcript=raw_transcript,
        guest_id=guest_id,
        stay_id=stay_id,
    )
    try:
        await process_welcome_call(req)
    except Exception:
        pass  # Don't fail silently but don't crash either


@app.post("/voice/elevenlabs-webhook")
async def elevenlabs_webhook(
    payload: ElevenLabsWebhookPayload,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Webhook endpoint called by ElevenLabs when a conversation ends.
    Returns 200 immediately and processes in the background.
    """
    background_tasks.add_task(_process_elevenlabs_webhook, payload)
    return {"received": True}


# ── PMS Webhook ───────────────────────────────────────────────────────────────
#
# This endpoint is called by your Property Management System (PMS) when a new
# reservation is created. It creates a Guest and Stay in the memory graph and
# returns a welcome link URL.
#
# In production you would also trigger SMS/email delivery here:
#   e.g. send_sms(guest_phone, welcome_link)
#   e.g. send_email(guest_email, welcome_link)

class PMSReservationPayload(BaseModel):
    reservation_id: str
    guest_name: str
    guest_email: str
    guest_phone: str | None = None
    room_type: str | None = None
    check_in: str
    check_out: str
    property_id: str = "sand-hill"


@app.post("/pms/reservation-created")
async def pms_reservation_created(body: PMSReservationPayload) -> dict:
    """
    Called by the PMS when a new reservation is confirmed.
    Creates (or finds) a Guest, creates a Stay, saves both to the graph,
    and returns a welcome link for sending to the guest.

    TODO: trigger SMS/email send here with the welcome_link.
    """
    from .graph.schema import ConsentLevel as CL

    # Find existing guest by email or create new
    existing = next(
        (g for g in graph.list_guests() if g.email == body.guest_email),
        None,
    )

    if existing:
        guest = existing
    else:
        name_parts = body.guest_name.strip().split()
        guest_id = "guest-" + body.guest_name.lower().replace(" ", "-").replace(".", "")
        guest = Guest(
            id=guest_id,
            name=body.guest_name,
            email=body.guest_email,
            phone=body.guest_phone or "",
            nationality="",
            home_city="",
            consent_level=CL.STANDARD,
            stays=[],
            preferences={},
        )
        graph.upsert_guest(guest)

    # Create stay
    stay_id = f"stay-{body.reservation_id.lower()}"
    stay = Stay(
        id=stay_id,
        guest_id=guest.id,
        property_id=body.property_id,
        check_in=body.check_in,
        check_out=body.check_out,
        room_type=body.room_type,
    )
    graph.upsert_stay(stay)

    # Add stay to guest's stay list
    if stay_id not in (guest.stays or []):
        if guest.stays is None:
            guest.stays = []
        guest.stays.append(stay_id)
        graph.upsert_guest(guest)

    graph.save()

    welcome_link = f"http://localhost:3000/welcome?stay_id={stay.id}"

    return {
        "guest_id": guest.id,
        "stay_id": stay.id,
        "welcome_link": welcome_link,
        "message": "Guest and stay created. Welcome link ready to send.",
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
