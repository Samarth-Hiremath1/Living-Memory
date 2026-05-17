"""
Weather lookup via wttr.in — no API key required.

wttr.in returns JSON with current conditions, temperature, wind, and humidity
for any city or location string. Used here as a zero-config demo data source.
"""

from __future__ import annotations
import httpx


def get_weather(location: str) -> str:
    """
    Fetch current weather for a city or location and return a plain-English summary.

    Returns an error string (not an exception) so the agent can handle failure gracefully.
    """
    if not location or not location.strip():
        return "Error: location cannot be empty."

    url = f"https://wttr.in/{location.strip().replace(' ', '+')}"

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"format": "j1"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return f"Error: weather request timed out for '{location}'."
    except httpx.HTTPStatusError as exc:
        return f"Error: weather service returned {exc.response.status_code} for '{location}'."
    except Exception as exc:
        return f"Error: could not fetch weather for '{location}' — {exc}"

    try:
        current = data["current_condition"][0]
        nearest = data.get("nearest_area", [{}])[0]

        temp_c = int(current["temp_C"])
        temp_f = int(current["temp_F"])
        feels_c = int(current["FeelsLikeC"])
        feels_f = int(current["FeelsLikeF"])
        desc = current["weatherDesc"][0]["value"]
        humidity = current["humidity"]
        wind_kmph = int(current["windspeedKmph"])
        wind_mph = round(wind_kmph * 0.621371)
        visibility_km = current.get("visibility", "?")

        # Try to get the canonical area name for a cleaner response
        area_name = location
        if nearest.get("areaName"):
            area_name = nearest["areaName"][0]["value"]

        return (
            f"Current weather in {area_name}: {desc}. "
            f"Temperature: {temp_c}°C / {temp_f}°F "
            f"(feels like {feels_c}°C / {feels_f}°F). "
            f"Humidity: {humidity}%. "
            f"Wind: {wind_kmph} km/h ({wind_mph} mph). "
            f"Visibility: {visibility_km} km."
        )
    except (KeyError, IndexError, ValueError) as exc:
        return f"Error: unexpected weather data format — {exc}"
