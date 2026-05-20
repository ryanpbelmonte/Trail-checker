"""OpenWeather integration for Trail Checker."""

import os

import requests

GEOCODING_URL = "http://api.openweathermap.org/geo/1.0/direct"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
REQUEST_TIMEOUT = 10


class GeocodeNotFoundError(Exception):
    """Raised when geocoding returns no matching locations."""


class ExternalAPIUnavailableError(Exception):
    """Raised on timeout, rate limit, bad key, or other upstream unavailability."""


class ExternalAPIError(Exception):
    """Raised when upstream returns malformed or unusable data."""


def get_api_key() -> str:
    key = os.environ.get("OPENWEATHER_API_KEY", "").strip()
    if not key:
        raise ExternalAPIUnavailableError("OpenWeather API key is not configured")
    return key


def geocode(query: str, api_key: str) -> dict:
    try:
        response = requests.get(
            GEOCODING_URL,
            params={"q": query, "limit": 1, "appid": api_key},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ExternalAPIUnavailableError("Geocoding service unavailable") from exc

    if response.status_code in (401, 429) or response.status_code != 200:
        raise ExternalAPIUnavailableError("Geocoding request failed")

    results = response.json()
    if not results:
        raise GeocodeNotFoundError(f"No location found for {query!r}")

    place = results[0]
    lat = place.get("lat")
    lon = place.get("lon")
    if lat is None or lon is None:
        raise ExternalAPIError("Geocoding response missing coordinates")

    return {
        "resolved_name": place.get("name", query),
        "latitude": lat,
        "longitude": lon,
        "country": place.get("country"),
        "state": place.get("state"),
    }


def fetch_weather(lat: float, lon: float, api_key: str) -> dict:
    try:
        response = requests.get(
            WEATHER_URL,
            params={
                "lat": lat,
                "lon": lon,
                "appid": api_key,
                "units": "imperial",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ExternalAPIUnavailableError("Weather service unavailable") from exc

    if response.status_code in (401, 429) or response.status_code != 200:
        raise ExternalAPIUnavailableError("Weather request failed")

    payload = response.json()
    try:
        weather = payload["weather"][0]
        main = payload["main"]
        temp_f = main["temp"]
        description = weather["description"]
        weather_main = weather["main"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalAPIError("Weather response missing required fields") from exc

    wind = payload.get("wind") or {}
    return {
        "main": weather_main,
        "description": description,
        "temp_f": temp_f,
        "feels_like_f": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "wind_mph": wind.get("speed"),
        "visibility_meters": payload.get("visibility"),
    }


def fetch_air_quality(lat: float, lon: float, api_key: str) -> dict | None:
    try:
        response = requests.get(
            AIR_POLLUTION_URL,
            params={"lat": lat, "lon": lon, "appid": api_key},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return None

    if response.status_code in (401, 429) or response.status_code != 200:
        return None

    try:
        entry = response.json()["list"][0]
        components = entry["components"]
        return {
            "aqi": entry["main"]["aqi"],
            "pm2_5": components.get("pm2_5"),
            "pm10": components.get("pm10"),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def compute_recommendation(weather: dict, air_quality: dict | None) -> str:
    aqi = air_quality.get("aqi") if air_quality else None
    wind = weather.get("wind_mph") or 0
    main = (weather.get("main") or "").lower()
    description = (weather.get("description") or "").lower()

    if aqi in (4, 5):
        return "poor"
    if "thunder" in main or "thunder" in description:
        return "poor"
    if wind >= 30:
        return "poor"

    if aqi == 3:
        return "caution"
    if any(word in description for word in ("rain", "snow", "drizzle")):
        return "caution"
    if wind >= 20:
        return "caution"

    visibility = weather.get("visibility_meters")
    if visibility is not None and visibility < 5000:
        return "caution"

    if aqi in (1, 2):
        return "good"
    if aqi is None:
        return "unknown"

    return "unknown"


def _build_conditions_payload(
    query_text: str,
    resolved_name: str,
    latitude: float,
    longitude: float,
    api_key: str,
    country: str | None = None,
    state: str | None = None,
) -> dict:
    """Fetch weather/AQI and build the shared conditions dict."""
    weather = fetch_weather(latitude, longitude, api_key)
    air_quality = fetch_air_quality(latitude, longitude, api_key)
    recommendation = compute_recommendation(weather, air_quality)

    return {
        "query_text": query_text,
        "resolved_name": resolved_name,
        "latitude": latitude,
        "longitude": longitude,
        "country": country,
        "state": state,
        "weather": weather,
        "air_quality": air_quality or {},
        "recommendation": recommendation,
    }


def get_conditions_for_query(query_text: str) -> dict:
    api_key = get_api_key()
    location = geocode(query_text, api_key)
    return _build_conditions_payload(
        query_text,
        location["resolved_name"],
        location["latitude"],
        location["longitude"],
        api_key,
        country=location.get("country"),
        state=location.get("state"),
    )


def get_conditions_for_coordinates(
    query_text: str,
    resolved_name: str,
    latitude: float,
    longitude: float,
    country: str | None = None,
    state: str | None = None,
) -> dict:
    """Fetch live conditions for known coordinates (saved-trail re-check)."""
    api_key = get_api_key()
    return _build_conditions_payload(
        query_text,
        resolved_name,
        latitude,
        longitude,
        api_key,
        country=country,
        state=state,
    )
