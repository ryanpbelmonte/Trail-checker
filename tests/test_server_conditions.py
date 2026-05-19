"""
Week 6 server-side contract tests for Trail Checker.

Owner: Ryan Belmonte — Server-side

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
from sqlmodel import SQLModel
from app import app, engine


@pytest.fixture
def client():
    app.config["TESTING"] = True

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with app.test_client() as client:
        yield client


@responses.activate
def test_api_conditions_returns_weather_air_quality_and_recommendation(client):
    """A valid query returns the agreed JSON envelope and condition fields."""
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
