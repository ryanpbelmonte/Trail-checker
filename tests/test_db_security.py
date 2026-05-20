"""
Week 6 DB-and-security contract tests for Trail Checker.

Owner: Nick Stjern - DB-and-security

These tests describe the agreed schema and authorization behavior. They
exercise the Flask-Login refactor, login-required enforcement, and the
ownership-based 404 contract from CONTRACTS.md.
"""

import pytest
from sqlmodel import SQLModel, Session, select

from app import app, engine, SavedTrail, User


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


def test_non_owner_delete_returns_404_for_missing_trail(client):
    """Deleting a non-existent trail must return 404 (does not leak existence)."""
    client.post("/register", data={"username": "alice", "password": "password123"})
    client.post("/logout")
    client.post("/register", data={"username": "bob", "password": "password123"})

    response = client.post("/saved-trails/999/delete")

    assert response.status_code == 404


def test_non_owner_delete_real_trail_returns_404(client):
    """A user deleting another user's *real* saved trail must receive 404."""
    client.post("/register", data={"username": "alice", "password": "password123"})

    client.post(
        "/saved-trails",
        data={
            "display_name": "Mount Rainier",
            "query_text": "Mount Rainier",
            "latitude": "46.8523",
            "longitude": "-121.7603",
        },
    )

    with Session(engine) as db:
        alice_trail = db.exec(select(SavedTrail)).first()
        assert alice_trail is not None
        alice_trail_id = alice_trail.id

    client.post("/logout")
    client.post("/register", data={"username": "bob", "password": "password123"})

    delete_response = client.post(f"/saved-trails/{alice_trail_id}/delete")
    assert delete_response.status_code == 404

    check_response = client.get(f"/saved-trails/{alice_trail_id}/check")
    assert check_response.status_code == 404

    with Session(engine) as db:
        still_there = db.get(SavedTrail, alice_trail_id)
        assert still_there is not None
        alice = db.exec(select(User).where(User.username == "alice")).first()
        assert still_there.user_id == alice.id


def test_saved_trail_unique_constraint_blocks_duplicate(client):
    """The composite unique constraint must reject duplicate saves at the DB layer."""
    client.post("/register", data={"username": "carol", "password": "password123"})

    payload = {
        "display_name": "Mount Rainier",
        "query_text": "Mount Rainier",
        "latitude": "46.8523",
        "longitude": "-121.7603",
    }

    client.post("/saved-trails", data=payload)
    client.post("/saved-trails", data=payload)

    with Session(engine) as db:
        rows = db.exec(select(SavedTrail)).all()
        assert len(rows) == 1


def test_cascade_delete_removes_users_saved_trails(client):
    """Deleting a user must cascade-delete that user's saved trails."""
    client.post("/register", data={"username": "dora", "password": "password123"})

    client.post(
        "/saved-trails",
        data={
            "display_name": "Mount Rainier",
            "query_text": "Mount Rainier",
            "latitude": "46.8523",
            "longitude": "-121.7603",
        },
    )

    with Session(engine) as db:
        dora = db.exec(select(User).where(User.username == "dora")).first()
        assert dora is not None
        trail_count_before = len(
            db.exec(select(SavedTrail).where(SavedTrail.user_id == dora.id)).all()
        )
        assert trail_count_before == 1

        db.delete(dora)
        db.commit()

        trail_count_after = len(
            db.exec(select(SavedTrail).where(SavedTrail.user_id == dora.id)).all()
        )
        assert trail_count_after == 0
