# Week 7 Role Work

One file at the repo root; each teammate owns a section below (Course 506 Part 2).

---

## Liam Sipp - Client-side

### Role

Client-side

### Files touched

- `templates/login.html`
- `templates/base.html`
- `app.py`
- `tests/test_auth.py`
- `tests/test_client_templates.py`
- `requirements.txt`

### What I changed

I updated the login page for the Week 7 OAuth flow by adding a visible **Sign in with GitHub** button while keeping the existing username/password login form. I also added a **Remember me** checkbox to the password login form using `name="remember"`, matching the Week 7 DB/security contract that reads this field in the login route.

I updated the authenticated navbar so it shows the stable contract text:

`Logged in as {username}`

This gives the Playwright tests a reliable user-visible target. I also kept logout as a POST form/button and updated the logout UX so logout redirects back to the login page.

The password login success redirect now lands on `/saved-trails`, which matches the team's Week 7 client-side UX decision.

### Tests added or updated

I updated the existing auth redirect test so it expects successful password login to redirect to `/saved-trails`.

I added client-side template tests that verify:

- the login page includes the **Sign in with GitHub** button
- the login page keeps the username/password form
- the login page includes the `remember` checkbox
- the authenticated navbar renders `Logged in as {username}`
- the authenticated navbar includes a POST logout button

Current non-e2e result:

`44 passed, 1 warning`

### Playwright test

**File:** `tests/e2e/test_client_oauth_ux.py`

**What it verifies:** A logged-out user opens `/login`, sees and clicks **Sign in with GitHub**, then the test accepts either the external GitHub redirect or the `TESTING=1` not-configured fallback. The test then uses `/test/login/LiamCase` to stand in for the completed OAuth session, verifies the user lands on `/saved-trails`, verifies the navbar shows `Logged in as LiamCase`, clicks **Logout**, and verifies the user returns to `/login`.

**Run locally:**

`docker compose exec app pytest tests/e2e -v`

Current result: `2 passed`


### Known gaps

This branch does not test the real GitHub redirect. The team contract uses the test-login backdoor for browser-based tests and documents the real GitHub provider as an external dependency. My client-side work does not implement OAuth callback behavior or the test-login backdoor; those are Ryan's server-side responsibilities.

---

## Ryan Belmonte - Server-side

**In PR #18** (`Week7-server-oauth`). Implements OAuth routes, test backdoor, e2e fixture, and CI Playwright wiring.

### Role

Server-side

### Files touched

- `app.py` - Authlib GitHub OAuth, create/link, `/test/login/<username>`
- `requirements.txt` - `Authlib`
- `tests/e2e/conftest.py` - `live_server`, file-backed SQLite for e2e
- `tests/e2e/test_server_oauth_login.py`
- `.github/workflows/test.yml` - Playwright browsers; e2e in separate pytest step

### What I implemented

- `GET /login/github` - starts Authorization Code flow when OAuth env is configured.
- `GET /auth/github/callback` - token exchange, GitHub `/user`, transactional create/link, `login_user`, redirect `/saved-trails`.
- `GET /test/login/<username>` - section 7a.6 backdoor (`TESTING=1` + localhost/debug only; else 404).
- OAuth session: `login_user` without `remember=True`; `session.permanent = True` (section 7a.7).
- **Startup:** non-`TESTING` runs require `GITHUB_OAUTH_CLIENT_ID` and `GITHUB_OAUTH_CLIENT_SECRET` or the app raises on import (section 7a.13). `TESTING=1` (pytest/CI) may omit them; `/login/github` then flashes and redirects to `/login`.

### Playwright test

**File:** `tests/e2e/test_server_oauth_login.py`

**Verifies:** Logged-out user hitting `/saved-trails` -> `/login`; `/test/login/alice` -> `/saved-trails` with `Logged in as alice` visible.

**Week 6 walkthrough adapted:** None (new Week 7 server path).

```bash
python3 -m playwright install chromium
TESTING=1 SECRET_KEY=test-secret-e2e pytest tests/e2e/ -q
```

### Known gaps

- CI/e2e do not call real GitHub (backdoor only).
- E2e does not assert `oauth_identity` row creation (Nick's unit tests + Part 3 lifecycle).

---

## Nick Stjern - DB-and-security

**Week 7 Part 2:** OAuth schema/session hardening (PR #15, merged to `main`) + Playwright protected-route lifecycle test (`db-sec-rolework`).

### Role

DB-and-security

### Files touched

**Week 7 schema / security (merged earlier):**

- `app.py` — `OAuthIdentity` model, nullable `users.password_hash`, session/cookie config (`PERMANENT_SESSION_LIFETIME`, `REMEMBER_COOKIE_DURATION`, `SESSION_PROTECTION="strong"`), `load_dotenv()`, login guards for OAuth-only users
- `requirements.txt` — `python-dotenv`
- `.env.example` — documents `SECRET_KEY`, `OPENWEATHER_API_KEY`, `GITHUB_OAUTH_*`
- `tests/test_db_security.py` — Week 7 schema and session/cookie assertions
- `tests/test_auth.py` — remember-me and `session.permanent` behavior
- `CONTRACTS.md` — §7a addendum (OAuth schema, linking policy, session/CSRF/backdoor contracts, §7a.12 navbar text)
- `coord_session.md` — implementation notes and coordination items
- `e2e/db-and-security.md` — manual E2E walk for schema, auth, ownership, secret hygiene

**Week 7 Playwright (this branch):**

- `tests/e2e/test_protected_routes.py` — browser-driven protected-page lifecycle test

### What I implemented

**N1–N7 (Week 7 DB-and-security block):**

- **N1** — `oauth_identity` table with `UNIQUE(provider, provider_user_id)`, provider whitelist check, non-empty `provider_user_id` check, indexed `user_id`, `ON DELETE CASCADE`
- **N2** — `users.password_hash` nullable for OAuth-only users; login route rejects NULL safely with constant-time behavior
- **N3** — No auto-link by email; each new GitHub identity creates a distinct user (enforced by schema + contract)
- **N4** — 12-hour session lifetime, 30-day remember-me cookie, `session.permanent = True` after login, `SESSION_PROTECTION="strong"`
- **N5** — CSRF remains enabled on all POST routes in non-test mode; no new exemptions
- **N6** — `python-dotenv`, `.env.example`, secret hygiene documented in README/CONTRACTS
- **N7** — E2E test plumbing: file-backed SQLite in `tests/e2e/conftest.py` (shared with Liam/Ryan; extended on `main` with `live_server`)

**Playwright slice (Part 2 grading criterion):**

- Verifies `/saved-trails` is **DOM-inaccessible** while anonymous, **accessible** after authentication, and **DOM-inaccessible again** after logout
- Uses the **password registration path** (`/register`), not GitHub OAuth, so the test does not depend on Ryan's Authlib wiring or live GitHub
- Uses the shared `live_server` fixture from `tests/e2e/conftest.py` (same threaded Werkzeug server as Liam and Ryan's tests)
- Asserts on rendered DOM via Playwright `expect`, including a no-leak check (`Your saved locations` count `0` when anonymous)

### Tests added or updated

**Unit / integration (`tests/test_db_security.py`, `tests/test_auth.py`):**

- `oauth_identity` table columns, constraints, cascade delete
- Nullable `password_hash`, OAuth-only user creation, NULL-password login rejection
- Session lifetime, remember cookie duration, `session_protection`, cookie security flags
- Existing Week 6 coverage retained: ownership rules, unique constraints, cascade delete, login-required routes

**Run locally (unit/integration only):**

```bash
TESTING=1 SECRET_KEY=test-secret pytest tests/ --ignore=tests/e2e -v
```

Current result on `main`: `44 passed, 1 warning` (after Liam's Week 7 client tests merged)

### Playwright test

**File:** `tests/e2e/test_protected_routes.py`

**What it verifies:**

1. **Anonymous** — `GET /saved-trails` shows the login form; protected heading `Your saved locations` does not appear in the DOM
2. **Authenticated** — register `e2e-protected` via `/register`, visit `/saved-trails`, page renders `Your saved locations` and navbar contains the username
3. **Logged out** — POST logout via navbar form, revisit `/saved-trails`, login form returns and protected DOM does not leak

**Run locally:**

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
TESTING=1 SECRET_KEY=test-secret-e2e pytest tests/e2e/test_protected_routes.py -v
```

Or the full e2e folder (includes Liam and Ryan's tests):

```bash
TESTING=1 SECRET_KEY=test-secret-e2e pytest tests/e2e -v
```

**Week 6 walkthrough adapted:** `e2e/db-and-security.md` (manual Postgres + browser walk; complementary to this automated Playwright test)

### Known gaps

- **No real GitHub OAuth in this Playwright test** — Ryan's `test_server_oauth_login.py` and Liam's `test_client_oauth_ux.py` cover the backdoor/OAuth UX path; mine uses password registration intentionally
- **No CSRF rejection scenario yet** — Part 3 `test_full_lifecycle.py` scenario 3 (POST without token) is separate work per team plan (`group_messages/message_2.md`)
- **No session-expiry scenario yet** — Part 3 scenario 4 (short `PERMANENT_SESSION_LIFETIME`, then blocked protected page) is separate work
- **Does not assert `oauth_identity` rows in the browser** — covered by unit tests in `tests/test_db_security.py` and Ryan's OAuth callback implementation
- **Navbar assertion uses username substring**, not the full `Logged in as {username}` string, so the test stays stable across Liam's template wording while still proving authenticated vs anonymous state

