# Week 7 Team Walkthrough

This file explains the Week 7 Part 3 Playwright lifecycle suite in plain language. The goal is to make the tests readable for a future teammate or reviewer: what each scenario does, what regression it protects against, and what the suite intentionally does not cover.

The shared lifecycle test file is `tests/e2e/test_full_lifecycle.py`.

The suite is built around the Week 7 contract:

- successful login lands on `/saved-trails`
- authenticated navbar text includes `Logged in as {username}`
- the test backdoor is `/test/login/<username>`
- `oauth_identity` connects a local `User` to a GitHub-style provider identity
- logout is local only and redirects to `/login`

## How to run the lifecycle suite

Run the lifecycle file:

    TESTING=1 SECRET_KEY=test-secret-e2e pytest tests/e2e/test_full_lifecycle.py -v

Run the full e2e folder:

    TESTING=1 SECRET_KEY=test-secret-e2e pytest tests/e2e/ -v

## Scenario 1: First-time OAuth-style login creates local identity state

**Owner:** Ryan

**Test:** `test_first_time_oauth_creates_identity`

### User-visible behavior

A first-time test user signs in through `/test/login/<username>`, which stands in for the completed GitHub OAuth callback. Ryan's test uses a fresh username shaped like `ryan_part3_<random>`. The browser lands on `/saved-trails`, and the navbar shows `Logged in as <username>`.

### Regression this catches

This catches a broken first-time OAuth-style create/link flow. Before login, the matching `oauth_identity` row count should be `0`. After login through the backdoor, the row count should be exactly `1` for `provider="github"` and `provider_user_id="test-<username>"`. It also catches redirect drift if login stops landing on `/saved-trails`.

### Known gap

This does not drive the real GitHub authorize page, token exchange, or `/user` provider response. The test-login backdoor stands in for everything after the OAuth callback establishes the local authenticated user.


## Scenario 2: Returning OAuth-style login reuses the same identity row

**Owner:** Ryan

**Test:** `test_returning_oauth_reuses_identity`

### User-visible behavior

The same test user logs in through `/test/login/lifecycle_part3`, lands on `/saved-trails`, logs out through the navbar, then logs in again through the same backdoor route. The browser should again land on `/saved-trails` and show `Logged in as lifecycle_part3`.

### Regression this catches

This catches duplicate identity creation on returning login. The first login should create exactly one `oauth_identity` row. The second login should reuse that same row, so the count stays `1` instead of increasing or failing on a uniqueness constraint.

### Known gap

This validates the app's post-OAuth local persistence behavior in test mode. It does not validate provider-side behavior on `github.com`, GitHub account switching, or real provider session state.


## Scenario 3: Tokenless POST is rejected by CSRF protection

**Owner:** Nick

**Test:** `test_csrf_rejects_post_without_token`

### User-visible behavior

The test logs in through the backdoor as `csrf_lifecycle`, then sends a direct POST request to `/logout` without a CSRF token. The app rejects the tokenless POST instead of logging the user out. After the rejected request, the browser can still visit `/saved-trails`, the saved-trails page still renders, and the navbar still shows `Logged in as csrf_lifecycle`.

### Regression this catches

This catches accidental weakening of CSRF protection on state-changing POST routes. If `/logout` accepted a POST without a CSRF token, the user would be logged out and the follow-up visit to `/saved-trails` would fail.

### Known gap

This scenario verifies CSRF rejection on `/logout` as the representative state-changing form. It does not exhaustively test every future POST route; new POST routes still need their own CSRF-aware forms and tests when added.


## Scenario 4: Expired session blocks protected page access

**Owner:** Nick

**Test:** `test_session_expires_and_blocks_protected_page`

### User-visible behavior

The test temporarily shortens `PERMANENT_SESSION_LIFETIME`, logs in through the backdoor as `session_expiry_lifecycle`, waits past the shortened lifetime, then tries to visit `/saved-trails`. The protected saved-trails content should no longer render, the login form should appear instead, and the navbar should no longer show the expired username.

### Regression this catches

This catches bugs where expired sessions are still treated as authenticated, protected pages remain visible after session expiry, or the app ignores the configured session lifetime.

### Known gap

This test uses a short test-only lifetime and a small wall-clock wait. It verifies the app's session-expiry behavior in the e2e test environment, but it does not cover every browser cookie edge case or long-running production session scenario.


## Overall suite gaps

The lifecycle suite intentionally does not test the real GitHub login page, real GitHub token exchange, or real GitHub `/user` response in CI. Those are external dependencies outside the repo, so the test-login backdoor is used for deterministic browser tests.

The e2e tests use a temporary SQLite database shared by the live Flask server and the test process. This is appropriate for repeatable CI tests, but it is not a full production Postgres deployment test.

The suite focuses on the Week 7 authentication lifecycle. It does not attempt to fully retest Trail Checker weather APIs, every saved-trail workflow, every browser, or every possible session/cookie edge case.

The suite depends on stable user-visible contract text, especially `Logged in as {username}`. If the UI intentionally changes that text, the contract and tests should be updated together.
