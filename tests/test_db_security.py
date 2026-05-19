"""
Week 6 DB-and-security contract tests for Trail Checker.

Owner: Nick Stjern — DB-and-security

These tests describe the agreed schema and authorization behavior before
implementation exists. They should fail at first, then pass when the
schema, Flask-Login refactor, and ownership rules are implemented.
"""

import os

# These must be set BEFORE importing app.py.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from sqlmodel import SQLModel
from app import app, engine


@pytest.fixture
def client():
    app.config["TESTING"] = True

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with app.test_client() as client:
        yield client


def test_saved_trails_table_exists_with_expected_columns(client):
    """The saved_trails table exists with the agreed contract columns."""
    tables = SQLModel.metadata.tables

    assert "saved_trails" in tables

    columns = tables["saved_trails"].columns.keys()
    expected_columns = {
        "id",
        "user_id",
        "display_name",
        "query_text",
        "latitude",
        "longitude",
        "country",
        "state",
        "notes",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(set(columns))


def test_trail_checks_table_exists_with_expected_columns(client):
    """The trail_checks table exists with the agreed contract columns."""
    tables = SQLModel.metadata.tables

    assert "trail_checks" in tables

    columns = tables["trail_checks"].columns.keys()
    expected_columns = {
        "id",
        "user_id",
        "query_text",
        "resolved_name",
        "latitude",
        "longitude",
        "weather_main",
        "weather_description",
        "temp_f",
        "feels_like_f",
        "humidity",
        "wind_mph",
        "visibility_meters",
        "aqi",
        "pm2_5",
        "pm10",
        "recommendation",
        "checked_at",
    }

    assert expected_columns.issubset(set(columns))


def test_anonymous_user_cannot_view_saved_trails(client):
    """Anonymous users must be blocked from the saved trails page."""
    response = client.get("/saved-trails")

    assert response.status_code in (302, 401)


def test_anonymous_user_cannot_save_trail(client):
    """Anonymous users must not be able to create saved trails."""
    response = client.post(
        "/saved-trails",
        data={
            "display_name": "Mount Rainier",
            "query_text": "Mount Rainier",
            "latitude": "46.8523",
            "longitude": "-121.7603",
        },
    )

    assert response.status_code in (302, 401)


def test_non_owner_delete_returns_404(client):
    """A user deleting another user's saved trail must receive 404, not 403."""
    client.post("/register", data={"username": "alice", "password": "password123"})
    client.post("/logout")
    client.post("/register", data={"username": "bob", "password": "password123"})

    response = client.post("/saved-trails/999/delete")

    assert response.status_code == 404
