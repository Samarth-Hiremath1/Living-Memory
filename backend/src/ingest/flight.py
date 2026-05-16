"""AviationStack flight client with cache fallback."""

from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..config import settings

_CACHE_FILE = Path("./data/flight_cache.json")
_CACHE_TTL = 120  # seconds


@dataclass
class FlightInfo:
    flight_number: str
    airline: str
    origin: str
    origin_iata: str
    destination: str
    destination_iata: str
    scheduled_departure: str
    scheduled_arrival: str
    estimated_arrival: str | None
    status: str  # scheduled / active / landed / cancelled / diverted
    delay_minutes: int | None
    gate: str | None
    terminal: str | None


def _load_cache() -> dict[str, Any]:
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(data: dict[str, Any]) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data, indent=2))


def get_flight_status(flight_number: str) -> FlightInfo | None:
    """Fetch flight status from AviationStack. Falls back to cache on failure."""
    cache = _load_cache()
    cache_key = flight_number.upper()

    # Return cached if fresh
    if cache_key in cache:
        cached_at = cache[cache_key].get("cached_at", 0)
        if time.time() - cached_at < _CACHE_TTL:
            return _parse_cached(cache[cache_key]["data"])

    if not settings.aviationstack_api_key:
        return _demo_flight(flight_number)

    try:
        url = "http://api.aviationstack.com/v1/flights"
        params = {
            "access_key": settings.aviationstack_api_key,
            "flight_iata": flight_number.upper(),
            "limit": 1,
        }
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        flights = data.get("data", [])
        if not flights:
            return _demo_flight(flight_number)

        flight = flights[0]
        info = _parse_aviationstack(flight)

        # Cache the result
        cache[cache_key] = {"cached_at": time.time(), "data": flight}
        _save_cache(cache)

        return info

    except Exception:
        # Fallback to stale cache or demo data
        if cache_key in cache:
            return _parse_cached(cache[cache_key]["data"])
        return _demo_flight(flight_number)


def _parse_aviationstack(flight: dict) -> FlightInfo:
    dep = flight.get("departure", {})
    arr = flight.get("arrival", {})
    fl = flight.get("flight", {})
    airline = flight.get("airline", {})

    delay = arr.get("delay")

    return FlightInfo(
        flight_number=fl.get("iata", ""),
        airline=airline.get("name", ""),
        origin=dep.get("airport", ""),
        origin_iata=dep.get("iata", ""),
        destination=arr.get("airport", ""),
        destination_iata=arr.get("iata", ""),
        scheduled_departure=dep.get("scheduled", ""),
        scheduled_arrival=arr.get("scheduled", ""),
        estimated_arrival=arr.get("estimated"),
        status=flight.get("flight_status", "scheduled"),
        delay_minutes=int(delay) if delay else None,
        gate=arr.get("gate"),
        terminal=arr.get("terminal"),
    )


def _parse_cached(data: dict) -> FlightInfo:
    return _parse_aviationstack(data)


def _demo_flight(flight_number: str) -> FlightInfo:
    """Deterministic demo flight for Anna Lindqvist's arrival into SFO."""
    return FlightInfo(
        flight_number=flight_number.upper(),
        airline="Lufthansa",
        origin="Frankfurt am Main Airport",
        origin_iata="FRA",
        destination="San Francisco International Airport",
        destination_iata="SFO",
        scheduled_departure="2024-09-15T10:30:00+02:00",
        scheduled_arrival="2024-09-15T13:15:00-07:00",
        estimated_arrival="2024-09-15T13:22:00-07:00",
        status="active",
        delay_minutes=7,
        gate="G92",
        terminal="International",
    )
