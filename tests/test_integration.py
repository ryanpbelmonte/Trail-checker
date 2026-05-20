"""
Week 6 integration contract tests for Trail Checker.

Owner: Shared - Cache Kings

This test describes the full user flow before implementation exists.
It should fail at first, then pass when the server-side, client-side,
and DB/security slices are integrated.
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
def test_logged_in_user_can_search_save_view_recheck_and_delete_trail(client):
    """Whole-system flow: login, search, save, view, re-check, and delete."""
    client.post(
        "/register",
        data={"username": "trailuser", "password": "password123"},
        follow_redirects=True,
    )

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

    results_response = client.get("/trail-checker/results?q=Mount%20Rainier")
    assert results_response.status_code == 200
    assert b"Mount Rainier" in results_response.data

    save_response = client.post(
        "/saved-trails",
        data={
            "display_name": "Mount Rainier",
            "query_text": "Mount Rainier",
            "latitude": "46.8523",
            "longitude": "-121.7603",
            "country": "US",
            "state": "Washington",
            "notes": "Test saved trail",
        },
        follow_redirects=True,
    )

    assert save_response.status_code == 200
    assert b"Mount Rainier" in save_response.data

    saved_response = client.get("/saved-trails")
    assert saved_response.status_code == 200
    assert b"Mount Rainier" in saved_response.data

    responses.add(
        responses.GET,
        "https://api.openweathermap.org/data/2.5/weather",
        json={
            "name": "Mount Rainier",
            "weather": [{"main": "Clear", "description": "clear sky"}],
            "main": {"temp": 51.0, "feels_like": 49.5, "humidity": 65},
            "wind": {"speed": 5.0},
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
                    "main": {"aqi": 1},
                    "components": {"pm2_5": 2.1, "pm10": 4.8},
                }
            ]
        },
        status=200,
    )

    recheck_response = client.get("/saved-trails/1/check")
    assert recheck_response.status_code == 200
    assert b'data-testid="weather-card"' in recheck_response.data
    assert b"Clear" in recheck_response.data
    assert b"This location is already saved." in recheck_response.data

    delete_response = client.post("/saved-trails/1/delete", follow_redirects=True)
    assert delete_response.status_code == 200

    final_saved_response = client.get("/saved-trails")
    assert final_saved_response.status_code == 200
    assert b"Mount Rainier" not in final_saved_response.data
