"""Pydantic models for the guest memory graph. Schema is Neo4j-compatible when migrating."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


class ConsentLevel(str, Enum):
    STANDARD = "standard"            # This stay only — no history stored after checkout
    LIVING_MEMORY = "living_memory"  # Full cross-property AI memory, travels with guest


class ObservationSource(str, Enum):
    STAFF_VOICE = "staff_voice"
    STAFF_TEXT = "staff_text"
    WELCOME_CALL = "welcome_call"
    PMS = "pms"
    SYNTHETIC = "synthetic"


class Observation(BaseModel):
    id: str = Field(default_factory=new_id)
    stay_id: str
    guest_id: str
    property_id: str
    raw_text: str
    structured: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    source: ObservationSource = ObservationSource.STAFF_TEXT
    staff_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sentiment: str | None = None  # positive / neutral / negative


class Stay(BaseModel):
    id: str = Field(default_factory=new_id)
    guest_id: str
    property_id: str
    check_in: str  # ISO date string
    check_out: str | None = None
    room_type: str | None = None
    room_number: str | None = None
    rate_code: str | None = None
    party_size: int = 1
    occasions: list[str] = Field(default_factory=list)  # e.g. ["anniversary", "business"]
    observations: list[str] = Field(default_factory=list)  # observation IDs
    flight_number: str | None = None
    notes: str | None = None


class Guest(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    email: str | None = None
    phone: str | None = None
    nationality: str | None = None
    languages: list[str] = Field(default_factory=list)
    home_city: str | None = None
    consent_level: ConsentLevel = ConsentLevel.STANDARD
    stays: list[str] = Field(default_factory=list)  # stay IDs
    preferences: dict[str, Any] = Field(default_factory=dict)
    # Cross-property identity aliases: {property_id: local_guest_id}
    property_aliases: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PlaceMaker(BaseModel):
    id: str = Field(default_factory=new_id)
    property_id: str
    name: str
    role: str
    location: str
    bio: str
    offerings: list[dict[str, Any]] = Field(default_factory=list)
    availability_windows: list[str] = Field(default_factory=list)
    ideal_guest_profiles: list[str] = Field(default_factory=list)
    photo_url: str | None = None
    contact: str | None = None


class Property(BaseModel):
    id: str
    name: str
    city: str
    country: str
    region: str | None = None
    character: str = ""  # narrative description of the property's soul
    cultural_calendar: list[dict[str, Any]] = Field(default_factory=list)
    signature_amenities: list[str] = Field(default_factory=list)
    room_amenity_options: list[str] = Field(default_factory=list)
    welcome_amenity_options: list[dict[str, Any]] = Field(default_factory=list)
    placemaker_ids: list[str] = Field(default_factory=list)


class ArrivalPlan(BaseModel):
    id: str = Field(default_factory=new_id)
    guest_id: str
    stay_id: str
    property_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    room_temperature_f: int | None = None
    welcome_amenity: str | None = None
    moments_to_create: list[str] = Field(default_factory=list)
    itinerary: list[dict[str, Any]] = Field(default_factory=list)
    placemaker_intro: str | None = None
    flight_status: str | None = None
    jet_lag_note: str | None = None
    raw_dossier: str = ""  # the full friend-filtered markdown dossier


class GraphStore(BaseModel):
    guests: dict[str, Guest] = Field(default_factory=dict)
    stays: dict[str, Stay] = Field(default_factory=dict)
    observations: dict[str, Observation] = Field(default_factory=dict)
    properties: dict[str, Property] = Field(default_factory=dict)
    placemakers: dict[str, PlaceMaker] = Field(default_factory=dict)
    arrival_plans: dict[str, ArrivalPlan] = Field(default_factory=dict)
