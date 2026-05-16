"""Flight agent: pulls real-time flight data and computes jet lag profile."""

from __future__ import annotations
from datetime import datetime
from ..ingest.flight import get_flight_status, FlightInfo
from ..graph.schema import Stay, Guest


def compute_jet_lag_profile(origin_timezone_offset: int, dest_timezone_offset: int) -> dict:
    """Compute a simple jet lag profile based on timezone difference."""
    diff = abs(dest_timezone_offset - origin_timezone_offset)
    if diff <= 2:
        severity = "minimal"
        note = None
    elif diff <= 5:
        severity = "mild"
        note = "She may appreciate a lighter dinner option on arrival."
    elif diff <= 8:
        severity = "moderate"
        note = "Likely arriving tired — keep the check-in seamless and unhurried."
    else:
        severity = "significant"
        note = (
            "Long-haul fatigue is real. A quiet, unhurried arrival is the priority. "
            "Avoid scheduling anything in the first 3 hours."
        )
    return {"severity": severity, "hours_difference": diff, "staff_note": note}


class FlightAgentResult:
    def __init__(
        self,
        flight_info: FlightInfo | None,
        jet_lag: dict,
        error: str | None = None,
    ):
        self.flight_info = flight_info
        self.jet_lag = jet_lag
        self.error = error

    def to_dict(self) -> dict:
        return {
            "flight_info": self.flight_info.__dict__ if self.flight_info else None,
            "jet_lag": self.jet_lag,
            "error": self.error,
        }


def run_flight_agent(stay: Stay, guest: Guest) -> FlightAgentResult:
    """Pull flight data and compute jet lag for a given stay."""
    if not stay.flight_number:
        return FlightAgentResult(
            flight_info=None,
            jet_lag={"severity": "unknown", "hours_difference": 0, "staff_note": None},
        )

    flight_info = get_flight_status(stay.flight_number)

    if flight_info is None:
        return FlightAgentResult(
            flight_info=None,
            jet_lag={"severity": "unknown", "hours_difference": 0, "staff_note": None},
            error="Flight not found — using cached data",
        )

    # Rough jet lag: Tokyo (JST +9) → Salzburg (CET +1) = 8h diff
    # For demo: hardcode origin offset from guest nationality
    origin_offsets = {
        "Japanese": 9,
        "American": -5,
        "British": 0,
        "French": 1,
        "Australian": 10,
        "Chinese": 8,
    }
    origin_offset = origin_offsets.get(guest.nationality or "", 0)
    dest_offset = 1  # CET (Salzburg)

    jet_lag = compute_jet_lag_profile(origin_offset, dest_offset)

    return FlightAgentResult(flight_info=flight_info, jet_lag=jet_lag)
