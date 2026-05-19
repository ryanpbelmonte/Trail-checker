"""
Week 6 client-side contract tests for Trail Checker.

Owner: Liam Sipp — Client-side

These tests intentionally describe the Trail Checker templates before the
implementation exists. They should fail at first, then pass when the
client-side templates and routes are implemented.
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


def test_trail_checker_page_has_search_form(client):
    """The Trail Checker page exposes the agreed search form."""
    response = client.get("/trail-checker")

    assert response.status_code == 200
    assert b'action="/trail-checker/results"' in response.data
    assert b'method="GET"' in response.data or b"method='GET'" in response.data
    assert b'name="q"' in response.data
    assert b'type="submit"' in response.data


def test_base_nav_links_to_trail_checker(client):
    """The shared navbar includes a link to the Trail Checker page."""
    response = client.get("/")

    assert response.status_code == 200
    assert b'href="/trail-checker"' in response.data


def test_results_page_has_stable_result_sections(client):
    """The results page includes stable selectors for client-side layout tests."""
    response = client.get("/trail-checker/results?q=Mount%20Rainier")

    assert response.status_code == 200
    assert b'data-testid="weather-card"' in response.data
    assert b'data-testid="air-quality-card"' in response.data
    assert b'data-testid="recommendation-badge"' in response.data


def test_saved_trails_page_has_empty_state(client):
    """Saved trails page includes an empty-state container."""
    response = client.get("/saved-trails")

    assert response.status_code in (200, 302)

    if response.status_code == 200:
        assert b'data-testid="saved-trails-empty"' in response.data
