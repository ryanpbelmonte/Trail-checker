"""Playwright e2e: protected-page accessibility across the login lifecycle.

Owner: Nick (DB-and-security slice).

Verifies that /saved-trails is:
  1. Inaccessible while anonymous (redirected to /login, no protected DOM)
  2. Accessible after login (renders saved-trails-specific DOM)
  3. Inaccessible again after logout (redirected back to /login)

All assertions go through the rendered DOM via Playwright's `expect`,
which is what the Week 7 grading criterion calls for. Uses the password
auth path (not OAuth) so the test does not depend on Ryan's Authlib
wiring — keeping Nick's slice deterministic in CI.

Uses the shared `live_server` fixture from tests/e2e/conftest.py (same
threaded Werkzeug server as Liam and Ryan's Playwright tests).
"""

from playwright.sync_api import Page, expect


def test_saved_trails_protected_then_accessible_then_protected_again(
    page: Page, live_server
) -> None:
    """The protected page must be DOM-inaccessible → accessible → inaccessible."""
    base = live_server.url

    # ---------------------------------------------------------------------
    # Phase 1 — Anonymous: protected DOM must NOT render
    # ---------------------------------------------------------------------
    page.goto(f"{base}/saved-trails")

    expect(page.locator("form[action$='/login']")).to_be_visible()
    expect(page.locator("input[name='username']")).to_be_visible()
    expect(page.locator("input[name='password']")).to_be_visible()
    expect(page.get_by_text("Your saved locations")).to_have_count(0)

    # ---------------------------------------------------------------------
    # Phase 2 — Register a fresh user via the live UI, then visit /saved-trails
    # ---------------------------------------------------------------------
    page.goto(f"{base}/register")
    page.fill("input[name='username']", "e2e-protected")
    page.fill("input[name='password']", "password123")
    with page.expect_navigation():
        page.click("button[type='submit']")

    page.goto(f"{base}/saved-trails")

    expect(page).to_have_url(f"{base}/saved-trails")
    expect(page.get_by_text("Your saved locations")).to_be_visible()
    expect(page.locator("nav")).to_contain_text("e2e-protected")

    logout_button = page.locator("nav form[action$='/logout'] button[type='submit']")
    expect(logout_button).to_be_visible()

    # ---------------------------------------------------------------------
    # Phase 3 — Log out via the navbar POST form
    # ---------------------------------------------------------------------
    with page.expect_navigation():
        logout_button.click(force=True)

    # ---------------------------------------------------------------------
    # Phase 4 — Protected DOM must NOT render again
    # ---------------------------------------------------------------------
    page.goto(f"{base}/saved-trails")

    expect(page.locator("form[action$='/login']")).to_be_visible()
    expect(page.get_by_text("Your saved locations")).to_have_count(0)
    expect(page.locator("nav")).not_to_contain_text("e2e-protected")
