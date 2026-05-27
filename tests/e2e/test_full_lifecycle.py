"""Week 7 Part 3 — full login lifecycle (four scenarios).

Team branch: week7-part3. Owners fill stubs marked in each test docstring.
Shared helpers below; change signatures in your PR if your test needs it.

Contract pins: post-login /saved-trails, navbar "Logged in as {username}",
backdoor /test/login/<username> per CONTRACTS.md §7a.6.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from sqlmodel import Session, select

from app import OAuthIdentity, engine

# Stable identity for scenarios 1–2 (Ryan). Use a fresh username per run if needed.
LIFECYCLE_USERNAME = "lifecycle_part3"
PROVIDER = "github"

# When the backdoor creates oauth_identity rows, use a deterministic provider_user_id.
# Until then, scenarios 1–2 may need a small app.py change on the backdoor route.
def provider_user_id_for_backdoor(username: str) -> str:
    """Expected oauth_identity.provider_user_id once backdoor writes identity rows."""
    return f"test-{username}"


def login_via_backdoor(page: Page, live_server, username: str = LIFECYCLE_USERNAME) -> None:
    """Browser login via §7a.6 test backdoor (stands in for OAuth callback)."""
    page.goto(f"{live_server.url}/test/login/{username}")
    expect(page).to_have_url(f"{live_server.url}/saved-trails")
    expect(page.get_by_text(f"Logged in as {username}")).to_be_visible()


def logout_via_ui(page: Page, live_server) -> None:
    """POST logout via navbar form (CSRF token included by the browser)."""
    page.goto(f"{live_server.url}/saved-trails")
    page.get_by_role("button", name="Logout").click()
    expect(page).to_have_url(f"{live_server.url}/login")


def count_oauth_identities(provider: str, provider_user_id: str) -> int:
    """Count rows in oauth_identity (test process shares e2e SQLite with live_server)."""
    with Session(engine) as db:
        rows = db.exec(
            select(OAuthIdentity).where(
                OAuthIdentity.provider == provider,
                OAuthIdentity.provider_user_id == provider_user_id,
            )
        ).all()
        return len(rows)


# ---------------------------------------------------------------------------
# Scenario 1 — Ryan: first-time OAuth login + oauth_identity row
# ---------------------------------------------------------------------------


def test_first_time_oauth_creates_identity(page: Page, live_server):
    """Ryan — first login via backdoor; post-login page; exactly one oauth_identity row."""
    pytest.skip("Ryan: implement scenario 1 (see provider_user_id_for_backdoor / backdoor note)")


# ---------------------------------------------------------------------------
# Scenario 2 — Ryan: returning login reuses row, no duplicate
# ---------------------------------------------------------------------------


def test_returning_oauth_reuses_identity(page: Page, live_server):
    """Ryan — logout and log in again; oauth_identity count stays 1."""
    pytest.skip("Ryan: implement scenario 2")


# ---------------------------------------------------------------------------
# Scenario 3 — Nick: CSRF rejects tokenless POST
# ---------------------------------------------------------------------------


def test_csrf_rejects_post_without_token(page: Page, live_server):
    """Nick — tokenless POST via page.request (or playwright.request) → rejected."""
    pytest.skip("Nick: implement scenario 3 — e.g. page.request.post(.../logout, data={})")


# ---------------------------------------------------------------------------
# Scenario 4 — Nick: session expires, protected page blocked
# ---------------------------------------------------------------------------


def test_session_expires_and_blocks_protected_page(page: Page, live_server):
    """Nick — short PERMANENT_SESSION_LIFETIME in test; /saved-trails inaccessible after expiry."""
    pytest.skip("Nick: implement scenario 4")
