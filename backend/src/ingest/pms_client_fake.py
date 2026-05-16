"""Fake PMS client — returns canned data for demo."""

from __future__ import annotations
from datetime import date, timedelta


def get_upcoming_arrivals(property_id: str, days_ahead: int = 1) -> list[dict]:
    """Return canned upcoming arrivals."""
    arrival_date = (date.today() + timedelta(days=days_ahead)).isoformat()
    return [
        {
            "pms_reservation_id": "RES-2024-09150001",
            "guest_name": "Anna Lindqvist",
            "arrival": arrival_date,
            "departure": (date.today() + timedelta(days=days_ahead + 5)).isoformat(),
            "room_type": "Lake View Suite",
            "flight": "JL43",
            "party_size": 1,
            "rate_code": "BAR",
        }
    ]


def get_in_house_guests(property_id: str) -> list[dict]:
    """Return canned in-house guests."""
    return [
        {
            "pms_reservation_id": "RES-2024-09150001",
            "guest_name": "Anna Lindqvist",
            "room": "214",
            "check_in": date.today().isoformat(),
            "check_out": (date.today() + timedelta(days=5)).isoformat(),
        }
    ]
