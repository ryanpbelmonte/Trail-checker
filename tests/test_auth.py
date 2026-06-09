"""
Course 506 Week 5 Skeleton — basic tests for the auth flow + S3 site routes.

These run in CI on every PR (see .github/workflows/test.yml) and locally with
`pytest` from the repo root. The pattern mirrors Week 4's regression test:
fast, automated, gates the merge.

Tests use SQLite in-memory so we don't need Postgres in CI. The Flask app
reads DATABASE_URL from env, so this override applies before the app loads.
"""

import os

# These must be set BEFORE importing app.py — environment-driven config.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from sqlmodel import SQLModel, select
from app import app, engine, User, Session


@pytest.fixture
def client():
    app.config["TESTING"] = True

    # Reset schema for each test — drop and recreate.
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with app.test_client() as client:
        yield client


def test_home_page_loads(client):
    """Home page is the trail checker landing with search form."""
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="trail-search"' in response.data
    assert b'action="/trail-checker/results"' in response.data
    assert b"My Site" not in response.data
    assert b"About" not in response.data


def test_login_page_renders(client):
    """The login form is reachable."""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"login" in response.data.lower()


def test_register_creates_user_in_database(client):
    """Registering a user writes a row to the users table."""
    client.post(
        "/register",
        data={"username": "alice", "password": "password123"},
    )

    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == "alice")).first()
        assert user is not None
        assert user.password_hash != "password123"  # password was hashed


def test_register_rejects_duplicate_username(client):
    """A second register with the same username flashes 'already taken'."""
    client.post("/register", data={"username": "bob", "password": "password123"})
    client.post("/logout")
    response = client.post(
        "/register",
        data={"username": "bob", "password": "different1"},
        follow_redirects=True,
    )
    assert b"already taken" in response.data


def test_login_with_wrong_password_shows_invalid(client):
    """Wrong password shows the 'Invalid' flash on the login page."""
    client.post("/register", data={"username": "dave", "password": "secret123"})
    client.post("/logout")

    response = client.post(
        "/login",
        data={"username": "dave", "password": "wrongpass1"},
        follow_redirects=True,
    )
    assert b"Invalid" in response.data


def test_login_redirects_saved_trails_with_session(client):
    """A successful login redirects to /saved-trails and sets the Flask-Login session."""
    client.post("/register", data={"username": "carol", "password": "secret123"})
    client.post("/logout")

    response = client.post(
        "/login",
        data={"username": "carol", "password": "secret123"},
    )
    assert response.status_code == 302
    assert response.location.endswith("/saved-trails")

    with client.session_transaction() as sess:
        assert "_user_id" in sess


def test_login_to_save_location_auto_saves_after_login(client):
    """Search -> log in to save -> saved-trails with location already saved."""
    client.post("/register", data={"username": "dana", "password": "password123"})
    client.post("/logout")

    prep = client.get(
        "/login/save-location",
        query_string={
            "display_name": "Mount Rainier",
            "query_text": "Mount Rainier",
            "latitude": "46.8523",
            "longitude": "-121.7603",
            "country": "US",
            "state": "Washington",
        },
        follow_redirects=False,
    )
    assert prep.status_code == 302
    assert "/login" in prep.location

    with client.session_transaction() as sess:
        assert sess["pending_saved_trail"]["display_name"] == "Mount Rainier"

    response = client.post(
        "/login",
        data={
            "username": "dana",
            "password": "password123",
            "next": "/saved-trails",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Trail saved" in response.data
    assert b"Mount Rainier" in response.data

    with client.session_transaction() as sess:
        assert "pending_saved_trail" not in sess


def test_queued_save_redirects_saved_trails_even_if_next_is_results(client):
    """Pending save wins over a stale next=results redirect target."""
    client.post("/register", data={"username": "frank", "password": "password123"})
    client.post("/logout")

    client.get(
        "/login/save-location",
        query_string={
            "display_name": "Yosemite",
            "query_text": "Yosemite",
            "latitude": "37.8651",
            "longitude": "-119.5383",
            "country": "US",
            "state": "California",
        },
    )

    response = client.post(
        "/login",
        data={
            "username": "frank",
            "password": "password123",
            "next": "/trail-checker/results?q=Yosemite",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.location.endswith("/saved-trails")


def test_register_after_login_to_save_also_persists_trail(client):
    """New account from login-to-save flow still saves the queued location."""
    prep = client.get(
        "/login/save-location",
        query_string={
            "display_name": "Seattle",
            "query_text": "Seattle",
            "latitude": "47.6062",
            "longitude": "-122.3321",
            "country": "US",
            "state": "Washington",
        },
        follow_redirects=False,
    )
    assert prep.status_code == 302

    response = client.post(
        "/register",
        data={
            "username": "newhiker",
            "password": "password123",
            "next": "/saved-trails",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Trail saved" in response.data
    assert b"Seattle" in response.data


def test_login_rejects_unsafe_external_next(client):
    """Open redirects via next are ignored; default to saved-trails."""
    client.post("/register", data={"username": "erin", "password": "password123"})
    client.post("/logout")

    response = client.post(
        "/login",
        data={
            "username": "erin",
            "password": "password123",
            "next": "https://evil.example/phish",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.location.endswith("/saved-trails")


def test_login_marks_session_permanent(client):
    """session.permanent=True must be set so PERMANENT_SESSION_LIFETIME applies."""
    client.post("/register", data={"username": "ed", "password": "password123"})
    client.post("/logout")

    client.post(
        "/login",
        data={"username": "ed", "password": "password123"},
    )

    with client.session_transaction() as sess:
        assert sess.permanent is True


def test_login_with_remember_me_issues_remember_cookie(client):
    """Submitting `remember` on the login form must trigger Flask-Login's remember cookie."""
    client.post("/register", data={"username": "fran", "password": "password123"})
    client.post("/logout")

    response = client.post(
        "/login",
        data={"username": "fran", "password": "password123", "remember": "on"},
    )

    cookies = response.headers.getlist("Set-Cookie")
    assert any("remember_token" in cookie.lower() for cookie in cookies)


def test_login_without_remember_me_issues_no_remember_cookie(client):
    """Without the remember checkbox, no remember_token cookie should be set."""
    client.post("/register", data={"username": "gus", "password": "password123"})
    client.post("/logout")

    response = client.post(
        "/login",
        data={"username": "gus", "password": "password123"},
    )

    cookies = response.headers.getlist("Set-Cookie")
    assert not any(
        "remember_token" in cookie.lower() and "max-age=0" not in cookie.lower()
        for cookie in cookies
    )
