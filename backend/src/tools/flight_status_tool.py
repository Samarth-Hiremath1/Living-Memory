"""
Flight status lookup — wraps the AviationStack ingest layer and
adds a hospitality-flavoured summary including jet lag severity.

Used by the MCP agent so staff can ask things like
"Is AA135 on time?" or "What's the jet lag situation for LH456?"
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..agents.flight_agent import compute_jet_lag_profile
from ..ingest.flight import get_flight_status as _fetch_flight


# Origin-airport IATA → IANA timezone name.
#
# Previously this was a dict of hardcoded integer UTC offsets, which was wrong
# for roughly half the year: FRA was pinned to +2 (CEST) but is +1 in winter,
# LHR to +1 but is 0 in winter, and the property was pinned to -7 (PDT) but is
# -8 in winter. Jet-lag severity for a Europe→California route could therefore
# be off by a full hour in each direction, which is enough to cross the
# "moderate" (<=8h) / "significant" (>8h) boundary and change the staff note.
#
# Offsets are now resolved from the IANA database at call time, so DST is
# handled by zoneinfo rather than by hand.
_IATA_TO_TZ: dict[str, str] = {
    # US Pacific
    "SFO": "America/Los_Angeles", "LAX": "America/Los_Angeles",
    "SEA": "America/Los_Angeles", "PDX": "America/Los_Angeles",
    # US Mountain / Central / Eastern
    "DEN": "America/Denver", "PHX": "America/Phoenix",  # Phoenix has no DST
    "ORD": "America/Chicago", "DFW": "America/Chicago", "IAH": "America/Chicago",
    "JFK": "America/New_York", "LGA": "America/New_York",
    "EWR": "America/New_York", "BOS": "America/New_York",
    "MIA": "America/New_York", "ATL": "America/New_York",
    # Europe
    "LHR": "Europe/London", "CDG": "Europe/Paris", "FRA": "Europe/Berlin",
    "MUC": "Europe/Berlin", "AMS": "Europe/Amsterdam", "ZRH": "Europe/Zurich",
    "FCO": "Europe/Rome", "MAD": "Europe/Madrid",
    # Middle East (no DST in Gulf states)
    "DXB": "Asia/Dubai", "DOH": "Asia/Qatar", "IST": "Europe/Istanbul",
    # Asia (none of these observe DST)
    "HKG": "Asia/Hong_Kong", "SIN": "Asia/Singapore", "NRT": "Asia/Tokyo",
    "HND": "Asia/Tokyo", "ICN": "Asia/Seoul", "PEK": "Asia/Shanghai",
    "PVG": "Asia/Shanghai", "BKK": "Asia/Bangkok",
    # Oceania (southern-hemisphere DST runs opposite to the north)
    "SYD": "Australia/Sydney", "MEL": "Australia/Melbourne",
    "AKL": "Pacific/Auckland",
    # Latin America
    "GRU": "America/Sao_Paulo", "EZE": "America/Argentina/Buenos_Aires",
    "MEX": "America/Mexico_City",
}

# Rosewood Sand Hill, Menlo Park CA. Resolved through zoneinfo, so this is
# PDT (-7) in summer and PST (-8) in winter automatically.
_PROPERTY_TZ = "America/Los_Angeles"


def _utc_offset_hours(tz_name: str, when: datetime | None = None) -> int | None:
    """
    Current UTC offset in whole hours for an IANA timezone.

    Returns None for an unknown zone rather than raising, so an unmapped
    airport degrades to "no jet lag note" instead of failing the tool call.
    """
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    moment = when or datetime.now(timezone.utc)
    offset = moment.astimezone(tz).utcoffset()
    if offset is None:
        return None
    return round(offset.total_seconds() / 3600)


def get_flight_info(flight_number: str) -> str:
    """
    Look up a flight by IATA number and return a concierge-ready summary.

    Includes status, scheduled vs. estimated arrival, terminal/gate if known,
    and a jet lag note based on the origin → SFO timezone difference.
    """
    if not flight_number or not flight_number.strip():
        return "Error: flight number cannot be empty."

    flight = _fetch_flight(flight_number.strip())
    if not flight:
        return f"No flight found for '{flight_number}'."

    lines: list[str] = []

    # Header line — airline + status
    status_label = {
        "scheduled": "scheduled",
        "active": "in the air",
        "landed": "landed",
        "cancelled": "CANCELLED",
        "diverted": "diverted",
    }.get(flight.status, flight.status)
    lines.append(
        f"Flight {flight.flight_number} ({flight.airline or 'unknown airline'}) — {status_label}."
    )

    # Route
    origin = flight.origin or flight.origin_iata or "unknown"
    dest = flight.destination or flight.destination_iata or "unknown"
    lines.append(f"Route: {origin} ({flight.origin_iata}) → {dest} ({flight.destination_iata}).")

    # Timing
    if flight.scheduled_arrival:
        lines.append(f"Scheduled arrival: {flight.scheduled_arrival}.")
    if flight.estimated_arrival and flight.estimated_arrival != flight.scheduled_arrival:
        lines.append(f"Estimated arrival: {flight.estimated_arrival}.")
    if flight.delay_minutes:
        delay_msg = (
            f"Delayed by {flight.delay_minutes} minutes."
            if flight.delay_minutes > 0
            else "Running ahead of schedule."
        )
        lines.append(delay_msg)

    # Gate / terminal
    if flight.terminal or flight.gate:
        gate_bits = []
        if flight.terminal:
            gate_bits.append(f"Terminal {flight.terminal}")
        if flight.gate:
            gate_bits.append(f"Gate {flight.gate}")
        lines.append("Arriving at: " + ", ".join(gate_bits) + ".")

    # Jet lag note (only useful for inbound flights to our property).
    # Both offsets are resolved at call time so DST is correct year-round.
    origin_tz = _IATA_TO_TZ.get((flight.origin_iata or "").upper())
    origin_offset = _utc_offset_hours(origin_tz) if origin_tz else None
    property_offset = _utc_offset_hours(_PROPERTY_TZ)
    if origin_offset is not None and property_offset is not None:
        jet_lag = compute_jet_lag_profile(origin_offset, property_offset)
        sev = jet_lag.get("severity", "unknown")
        hours = jet_lag.get("hours_difference", 0)
        note = jet_lag.get("staff_note")
        lines.append(f"Jet lag severity: {sev} ({hours}h timezone difference).")
        if note:
            lines.append(f"Staff note: {note}")

    return " ".join(lines)
