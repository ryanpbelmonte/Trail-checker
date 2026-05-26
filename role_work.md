# Week 7 Role Work

One file at the repo root; each teammate owns a section below (Course 506 Part 2).

---

## Liam Sipp — Client-side

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

The password login success redirect now lands on `/saved-trails`, which matches the team’s Week 7 client-side UX decision.

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

### Playwright status

The required Playwright test for my client-side slice depends on Ryan’s Week 7 routes:

- `/login/github`
- `/test/login/<username>`

Those routes are not present in my branch yet, so I did not add the final Playwright test in this commit. Once Ryan’s OAuth initiator route and test-login backdoor land, my Playwright test should cover this user-visible flow:

1. logged-out user opens `/login`
2. user sees and clicks **Sign in with GitHub**
3. test completes login through `/test/login/<username>`
4. user lands on `/saved-trails`
5. navbar shows `Logged in as {username}`
6. user clicks **Logout**
7. user lands on `/login`

### Known gaps

This branch does not test the real GitHub redirect. The team contract uses the test-login backdoor for browser-based tests and documents the real GitHub provider as an external dependency. This branch also does not implement OAuth callback behavior or the test-login backdoor because those are Ryan’s server-side responsibilities.

---

## Ryan Belmonte — Server-side

**In PR #18** (`Week7-server-oauth`). Implements OAuth routes, test backdoor, e2e fixture, and CI Playwright wiring.

### Role

Server-side

### Files touched

- `app.py` — Authlib GitHub OAuth, create/link, `/test/login/<username>`
- `requirements.txt` — `Authlib`
- `tests/e2e/conftest.py` — `live_server`, file-backed SQLite for e2e
- `tests/e2e/test_server_oauth_login.py`
- `.github/workflows/test.yml` — Playwright browsers; e2e in separate pytest step

### What I implemented

- `GET /login/github` — starts Authorization Code flow when OAuth env is configured.
- `GET /auth/github/callback` — token exchange, GitHub `/user`, transactional create/link, `login_user`, redirect `/saved-trails`.
- `GET /test/login/<username>` — §7a.6 backdoor (`TESTING=1` + localhost/debug only; else 404).
- OAuth session: `login_user` without `remember=True`; `session.permanent = True` (§7a.7).
- **Startup:** non-`TESTING` runs require `GITHUB_OAUTH_CLIENT_ID` and `GITHUB_OAUTH_CLIENT_SECRET` or the app raises on import (§7a.13). `TESTING=1` (pytest/CI) may omit them; `/login/github` then flashes and redirects to `/login`.

### Playwright test

**File:** `tests/e2e/test_server_oauth_login.py`

**Verifies:** Logged-out user hitting `/saved-trails` ? `/login`; `/test/login/alice` ? `/saved-trails` with `Logged in as alice` visible.

**Week 6 walkthrough adapted:** None (new Week 7 server path).

```bash
python3 -m playwright install chromium
TESTING=1 SECRET_KEY=test-secret-e2e pytest tests/e2e/ -q
```

### Known gaps

- CI/e2e do not call real GitHub (backdoor only).
- E2e does not assert `oauth_identity` row creation (Nick’s unit tests + Part 3 lifecycle).
