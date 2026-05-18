"""
Flight status lookup — wraps the AviationStack ingest layer and
adds a hospitality-flavoured summary including jet lag severity.

Used by the MCP agent so staff can ask things like
"Is AA135 on time?" or "What's the jet lag situation for LH456?"
"""

from __future__ import annotations

from ..agents.flight_agent import compute_jet_lag_profile
from ..ingest.flight import get_flight_status as _fetch_flight


# Rough origin-airport-IATA → UTC offset map for jet lag estimation.
# Only used when we don't have a recorded guest origin.
_IATA_TO_OFFSET: dict[str, int] = {
    "SFO": -7, "LAX": -7, "SEA": -7, "PDX": -7,  # US Pacific
    "JFK": -4, "LGA": -4, "EWR": -4, "BOS": -4, "MIA": -4,  # US Eastern
    "ORD": -5, "DFW": -5, "ATL": -4, "IAH": -5,  # US Central/Eastern
    "DEN": -6, "PHX": -7,
    "LHR": 1, "CDG": 2, "FRA": 2, "MUC": 2, "AMS": 2, "ZRH": 2, "FCO": 2, "MAD": 2,  # Europe
    "DXB": 4, "DOH": 3, "IST": 3,
    "HKG": 8, "SIN": 8, "NRT": 9, "HND": 9, "ICN": 9, "PEK": 8, "PVG": 8, "BKK": 7,
    "SYD": 10, "MEL": 10, "AKL": 12,
    "GRU": -3, "EZE": -3, "MEX": -6,
}

# Sand Hill (the demo property) → PDT
_PROPERTY_OFFSET = -7


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

    # Jet lag note (only useful for inbound flights to our property)
    origin_offset = _IATA_TO_OFFSET.get(flight.origin_iata or "")
    if origin_offset is not None:
        jet_lag = compute_jet_lag_profile(origin_offset, _PROPERTY_OFFSET)
        sev = jet_lag.get("severity", "unknown")
        hours = jet_lag.get("hours_difference", 0)
        note = jet_lag.get("staff_note")
        lines.append(f"Jet lag severity: {sev} ({hours}h timezone difference).")
        if note:
            lines.append(f"Staff note: {note}")

    return " ".join(lines)
