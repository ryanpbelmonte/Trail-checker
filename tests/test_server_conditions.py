"""
Week 6 server-side contract tests for Trail Checker.

Owner: Ryan Belmonte - Server-side

These tests describe the agreed API behavior before implementation exists.
They should fail at first, then pass when the server-side routes and
OpenWeather integration are implemented.
"""

import os

# These must be set BEFORE importing app.py.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["OPENWEATHER_API_KEY"] = "fake-test-key"

import pytest
import responses
from sqlmodel import SQLModel, Session, select
from app import SavedTrail, TrailCheck, app, engine


@pytest.fixture
def client():
    app.config["TESTING"] = True

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with app.test_client() as client:
        yield client


def add_openweather_responses(include_geocode=True):
    """Register the standard successful OpenWeather response set."""
    if include_geocode:
        responses.add(
            responses.GET,
            "http://api.openweathermap.org/geo/1.0/direct",
            json=[
                {
                    "name": "Mount Rainier",
                    "lat": 46.8523,
                    "lon": -121.7603,
                    "country": "US",
                    "state": "Washington",
                }
            ],
            status=200,
        )
    responses.add(
        responses.GET,
        "https://api.openweathermap.org/data/2.5/weather",
        json={
            "name": "Mount Rainier",
            "weather": [{"main": "Clouds", "description": "overcast clouds"}],
            "main": {"temp": 48.2, "feels_like": 45.1, "humidity": 72},
            "wind": {"speed": 8.3},
            "visibility": 10000,
        },
        status=200,
    )

    responses.add(
        responses.GET,
        "http://api.openweathermap.org/data/2.5/air_pollution",
        json={
            "list": [
                {
                    "main": {"aqi": 2},
                    "components": {"pm2_5": 4.2, "pm10": 7.5},
                }
            ]
        },
        status=200,
    )


@responses.activate
def test_api_conditions_returns_weather_air_quality_and_recommendation(client):
    """A valid query returns the agreed JSON envelope and condition fields."""
    add_openweather_responses()

    response = client.get("/api/conditions?q=Mount%20Rainier")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "weather" in payload["data"]
    assert "air_quality" in payload["data"]
    assert "recommendation" in payload["data"]


def test_api_conditions_rejects_short_query(client):
    """A missing or too-short query returns invalid_input."""
    response = client.get("/api/conditions?q=M")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_input"


@responses.activate
def test_api_conditions_returns_not_found_for_empty_geocoding_result(client):
    """No geocoding match returns not_found."""
    responses.add(
        responses.GET,
        "http://api.openweathermap.org/geo/1.0/direct",
        json=[],
        status=200,
    )

    response = client.get("/api/conditions?q=NoSuchTrailProbably")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_found"


@responses.activate
def test_results_page_persists_trail_check_for_anonymous_search(client):
    """Successful HTML searches create trail_checks audit rows."""
    add_openweather_responses()

    response = client.get("/trail-checker/results?q=Mount%20Rainier")

    assert response.status_code == 200
    with Session(engine) as db:
        rows = db.exec(select(TrailCheck)).all()

    assert len(rows) == 1
    assert rows[0].user_id is None
    assert rows[0].query_text == "Mount Rainier"
    assert rows[0].resolved_name == "Mount Rainier"
    assert rows[0].recommendation == "good"


@responses.activate
def test_results_page_marks_existing_saved_trail(client):
    """Logged-in users see already-saved state for matching coordinates."""
    client.post("/register", data={"username": "hiker", "password": "password123"})
    client.post(
        "/saved-trails",
        data={
            "display_name": "Mount Rainier",
            "query_text": "Mount Rainier",
            "latitude": "46.8523",
            "longitude": "-121.7603",
        },
    )
    add_openweather_responses()

    response = client.get("/trail-checker/results?q=Mount%20Rainier")

    assert response.status_code == 200
    assert b"This location is already saved." in response.data


@responses.activate
def test_saved_trail_recheck_uses_coordinates_without_geocoding(client):
    """Saved-trail recheck uses stored lat/lon and skips geocoding."""
    client.post("/register", data={"username": "hiker", "password": "password123"})
    client.post(
        "/saved-trails",
        data={
            "display_name": "Mount Rainier",
            "query_text": "Mount Rainier",
            "latitude": "46.8523",
            "longitude": "-121.7603",
            "country": "US",
            "state": "Washington",
        },
    )
    add_openweather_responses(include_geocode=False)

    response = client.get("/saved-trails/1/check")

    assert response.status_code == 200
    assert b'data-testid="weather-card"' in response.data
    assert b"This location is already saved." in response.data
    assert len(responses.calls) == 2
    assert all("geo/1.0/direct" not in call.request.url for call in responses.calls)

    with Session(engine) as db:
        saved = db.exec(select(SavedTrail)).first()
    assert saved is not None
