# Week 6 Coordinator / Planning Session

Team: Cache Kings  
Project: Trail Checker  
Repo: https://github.com/TCSS506-CacheKings/Trail-checker

## Participants

- Liam Sipp ? Client-side
- Ryan Belmonte ? Server-side
- Nick Stjern ? DB-and-security

## Context

Our team is using a three-person structure, so we do not have a separate coordinator role. We are sharing the coordinator responsibilities across the three roles.

We started by getting the Week 5 Flask/Postgres skeleton into the team repo, enabling the JavaScript submit-button fix, confirming the repo settings, and turning on branch protection / CI rules. After that, we moved into the Week 6 contract step.

## Questions we needed to answer

1. What should the Trail Checker MVP actually do for Week 6?
2. Which external API should we use?
3. What routes does the app need?
4. What data should be stored in Postgres?
5. What does each role own?
6. What tests need to exist before implementation starts?

## Decisions made

### Project scope

We agreed to keep the MVP small and realistic for Week 6.

The app will let a user search for a trailhead or outdoor location, check current weather and air quality, and display a simple trail-readiness recommendation.

Logged-in users can save locations, view saved locations, re-check them, and delete them.

### External API

We chose OpenWeather as the primary external API because it supports:

- Geocoding a location name into coordinates
- Current weather by latitude and longitude
- Air pollution / AQI by latitude and longitude

This keeps the external API integration realistic while avoiding a larger trail database integration for Week 6.

### Role ownership

Ryan owns server-side work:

- Flask routes
- OpenWeather API calls
- Request/response behavior
- API error handling

Liam owns client-side work:

- Templates
- Bootstrap layout
- Forms
- Navigation links
- Stable selectors for client-side tests

Nick owns DB-and-security work:

- SQLModel schema
- Flask-Login refactor
- Ownership rules
- Login-required behavior
- Secret hygiene

### Testing setup

We realized that listing the tests inside CONTRACTS.md is not enough. The Week 6 test files need to actually exist under the `tests/` folder.

We decided to add these files before role implementation:

- `tests/test_server_conditions.py`
- `tests/test_db_security.py`
- `tests/test_client_templates.py`
- `tests/test_integration.py`

These tests are expected to fail at first because the app has not implemented the Trail Checker features yet.

## Pushback / revisions

We intentionally avoided making the MVP too large.

Things we decided not to include in Week 6:

- Full trail database
- Official trail closure status
- Map UI
- Autocomplete
- Background refresh
- OAuth
- Public sharing of saved trails

We also discussed that the README/About/CONTRACTS files need to stay aligned so the project does not describe two different MVPs.

## Next step

The next setup step is to add the four Week 6 test files under `tests/`. After those files are committed in this branch, the team can review this setup PR before individual role implementation starts.

## DB-and-security slice (Nick) ? implementation notes

The slice landed in `app.py`, `requirements.txt`, the existing auth templates, and `tests/test_db_security.py`. Key changes:

- Flask-Login replaces raw `session["user_id"]`. The session cookie now carries `_user_id` and `_fresh`.
- New SQLModel models `SavedTrail` and `TrailCheck` are defined with database-level constraints (`NOT NULL`, FK with `ondelete="CASCADE"` on `saved_trails`, FK with `ondelete="SET NULL"` on `trail_checks`, and composite `UniqueConstraint(user_id, latitude, longitude)`).
- `@login_required` guards `/saved-trails`, `POST /saved-trails`, `POST /saved-trails/<id>/delete`, and `GET /saved-trails/<id>/check`.
- Ownership lookups always filter by `id AND user_id`, returning `404` (not `403`) when the row does not exist or belongs to another user.
- CSRF protection via Flask-WTF is enabled on every state-changing route. A custom `CSRFError` handler redirects anonymous CSRF failures to `/login`.
- Cookie flags `HTTPONLY`, `SAMESITE=Lax`, and `SECURE=not debug` are set for both session and remember-me cookies.
- A startup check refuses to boot with the default `SECRET_KEY` outside of debug/testing.
- Login is rate-limited to 10 POSTs per minute per IP via Flask-Limiter.
- `register` enforces a password policy of 8-128 characters with at least one letter and one digit.
- `login` runs `check_password_hash` against a dummy hash when the username does not exist, removing the username-enumeration timing oracle.
- An `audit` logger emits structured events for register, login success/failure, logout, and saved-trail create/delete/denied actions.

### Coordination items for the other roles

- Liam: template work remains ? `templates/trail_checker.html`, `templates/trail_results.html`, and `templates/saved_trails.html` are not yet present. Every POST form Liam adds must include `{{ csrf_token() }}` (see the existing `login.html`, `register.html`, and the navbar logout form in `base.html` for reference).
- Liam: when `saved_trails.html` is added, render the `prior_input` template variable to repopulate the form after a validation error.
- Ryan: `check_saved_trail` currently renders the saved trail data with `recommendation="unknown"`. Wire it to the live OpenWeather fetch when the server-side slice lands.
- Ryan: `/api/conditions` JSON envelope and `trail_checks` insertion remain in the server-side slice. The `TrailCheck` model and its schema are ready.

### Known follow-ups not in scope for Week 6

- Migrate from `SQLModel.metadata.create_all` to Alembic so schema changes do not require `docker compose down -v`.
- Move password hashing from werkzeug's PBKDF2 default to Argon2 via `argon2-cffi`.
- Add Content Security Policy, X-Frame-Options, and X-Content-Type-Options headers (e.g. Flask-Talisman).
- HSTS once HTTPS is enforced in front of the app.
- Pwned Passwords API check during register.
- Persistent rate-limit storage (Redis) and IP-based abuse detection.

## Week 7 DB-and-security slice (Nick) ? implementation notes

Slice landed across `app.py`, `requirements.txt`, `.env.example`, `tests/test_db_security.py`, `tests/test_auth.py`, and new `tests/e2e/conftest.py`. Reference CONTRACTS.md §7a for the authoritative contract.

### What changed in code

- **N6** `python-dotenv` added to `requirements.txt`. `app.py` calls `load_dotenv()` before any `os.environ` read so bare-metal `flask run` / `pytest` see the same env as Docker Compose. `.env.example` rewritten to list every required variable including the new `GITHUB_OAUTH_CLIENT_ID` and `GITHUB_OAUTH_CLIENT_SECRET`.
- **N1** New `OAuthIdentity` SQLModel with `UNIQUE(provider, provider_user_id)`, `ON DELETE CASCADE` on `user_id`, `index=True` on `user_id` (for fast reverse lookups and fast CASCADE), `CheckConstraint("provider IN ('github')")` to block case-variant duplicates, and `CheckConstraint("length(provider_user_id) > 0")`.
- **N2** `User.password_hash` is now `nullable=True` (typed `str | None`). The login route rejects `password_hash IS NULL` users without crashing and still runs the dummy hash to keep response timing constant.
- **N3** Enforced by N1's unique constraint + the lack of any email-based linking column. No code beyond the schema; the policy lives in CONTRACTS.md §7a.2.
- **N4** Added `PERMANENT_SESSION_LIFETIME = timedelta(hours=12)` and `REMEMBER_COOKIE_DURATION = timedelta(days=30)` to `app.config`. Set `login_manager.session_protection = "strong"`. `session.permanent = True` is set after every `login_user(...)` so the 12h lifetime actually applies. Login route now reads the `remember` form field.
- **N5** No new exempt routes. Verified by `git grep 'method="post"'` vs `git grep csrf_token()` in templates.
- **N7** New `tests/e2e/conftest.py` uses a per-pytest-session tempfile SQLite path (`tempfile.gettempdir() + uuid4().hex + ".db"`, chmod 0600) so concurrent runs cannot collide and `/tmp` is not used as a shared world-readable surface. `pytest_sessionfinish` cleans up.

### Coordination items for Ryan

- The `OAuthIdentity` model is importable as `from app import OAuthIdentity`. Use `(provider="github", provider_user_id=str(github_user_id))` ? the CHECK constraint will reject any other case or empty value.
- Callback **must** use a single transaction for the lookup-or-create flow and handle `IntegrityError` on the unique constraint as "concurrent callback won the race" (re-SELECT). See CONTRACTS.md §7a.3.
- Callback **must** use Authlib's built-in `state` validation. See §7a.4.
- Callback **must** be rate-limited at the same rate as `/login` (`10 per minute`). See §7a.5.
- `/test/login/<username>` backdoor must have three independent gates (TESTING + (debug OR localhost host) + 404-on-failure). See §7a.6.
- OAuth login: always call `login_user(user, remember=True)` followed by `session.permanent = True`.

### Coordination items for Liam

- Login form should add a `<input type="checkbox" name="remember">` and label. The login route reads `request.form.get("remember")`; any truthy value (e.g. `"on"`) triggers `remember=True`.
- No template change is needed for OAuth's "Sign in with GitHub" button beyond `<a href="{{ url_for('login_github') }}">` once Ryan's route exists.

### Operational note for the first Week 7 deploy

Making `users.password_hash` nullable is a destructive schema change for an existing Postgres database under `SQLModel.metadata.create_all`. First deploy requires:

```bash
docker compose down -v
docker compose up -d --build
```

SQLite test runs are unaffected (fresh DB per run). This requirement is also captured in CONTRACTS.md §7a.11.

### Week 7 known follow-ups not in scope

- Persist audit log to a `security_events` table or a mounted file (currently stdout-only, recycled on container restart).
- Session invalidation on password change (Flask-Login does not handle this out of the box; needs a `session_version` field on `User` or `SECRET_KEY` rotation).
- Pre-commit hook to scan `.env.example` for accidentally-real secret values.
- Postgres `sslmode=require` once the DB ever moves off the in-Compose network.
- Account-deletion UI (CASCADE handles the data side, but no user-facing flow exists).

---

## Week 7 OAuth planning (Ryan facilitated)

Date: Sunday May 24, 2026 (kicked off); finalized Monday May 25, 2026.
Facilitator: Ryan Belmonte.

### Context

Week 7 adds GitHub OAuth, Playwright browser-driven E2E tests, and session hardening. Cache Kings is a three-person team without a dedicated coordinator, so Part 1 contract work is shared. Ryan ran a pre-decided, role-blocked checklist in Discord (the "APPROVE YOUR BLOCK" message) instead of a live planning call to fit the 3-day window over a holiday weekend.

### Approval status

- **Nick (DB-and-security)** ? Approved N1?N7 on Sunday May 24, 2026. Implementation landed via PR #15 (squash-merged to `main`): `oauth_identity` schema, nullable `users.password_hash`, session/cookie config, CSRF, `.env.example`, `tests/e2e/conftest.py`, Week 7 contract addendum §7a.
- **Liam (Client-side)** ? Approved L1?L5 on Monday May 25, 2026: post-login redirect to `/saved-trails`, navbar text `Logged in as {username}`, remember-me on password form only, logout POST ? `/login`. Implementation pending on branch `week7-client-oauth-ux` (needs rebase on main before merge so we don't drop `e2e/whole_system.md`).
- **Ryan (Server-side)** ? R1?R7 self-documented in the kickoff message. Implementation planned on branch `week7-server-oauth` after Part 1 gap-fill lands.

### Cross-role implications (the integration edges)

These are the places where one role's work depends on or constrains another's. They are the contract surface the team has to keep aligned during implementation. Each item maps to a specific failure mode if the contract is violated.

1. **Schema must land before the callback.** Ryan's `/auth/github/callback` writes to `oauth_identity` and `users`. If the callback ships before Nick's migration, create/link crashes. Mitigation: Nick's PR merged first; Ryan's branch builds on top of it.

2. **Lookup key is `provider_user_id`, never email or `login`.** Study guide §3 is explicit. If we ever key on a mutable identifier, a GitHub username rename or email change orphans the local account. Enforced at schema level by `UNIQUE(provider, provider_user_id)` in §7a.1 and at code level by the callback contract in §7a.14.

3. **Nullable `password_hash` is load-bearing.** OAuth-only users have no password. The login route must refuse `password_hash IS NULL` without crashing and must still run the dummy hash to preserve timing parity. Implemented in Nick's PR.

4. **CSRF tokens on every new POST form.** If Liam adds any state-changing form without `{{ csrf_token() }}`, the Part 3 CSRF-rejection scenario fails for that form. Logout already CSRF-protected and stays POST per L4.

5. **Backdoor presence is gating.** All three Part 2 Playwright tests and all four Part 3 scenarios depend on `/test/login/<username>` returning a normal redirect in test mode. If the route is missing, mis-guarded, or returns 404 in `TESTING=1`, every Playwright test fails at the first navigation. Implementation is Ryan's per §7a.6.

6. **`conftest.py` must run before app import.** `tests/e2e/conftest.py` sets `TESTING=1`, `DATABASE_URL` (per-session SQLite tempfile), and `SECRET_KEY` *before* any module imports `app.py`. Already correct in Nick's PR.

7. **Post-login redirect target is pinned to `/saved-trails`.** All three roles' Playwright tests assert behavior after this redirect. Changing the target breaks every test; the change requires a contract amendment first.

8. **Logout redirect target is pinned to `/login`.** Used by the DB-security Playwright test and Part 3 session/logout scenarios.

9. **Navbar text contract ? `Logged in as {username}` ? is pinned.** Per §7a.12. Playwright assertions are pinned to this exact string. Any styling that splits the string across DOM nodes breaks `to_contain_text` assertions; Liam owns the rendering, Ryan owns ensuring `User.username` is non-empty before `login_user(...)` is called.

### Cross-role drift resolved at finalization

- §7a.7 originally said "OAuth login is always `remember=True`." Team-agreed L5 says remember-me is on the password form only and OAuth uses the normal session lifetime. The OAuth bullet has been rewritten in §7a.7 (Ryan's implementation will call `login_user(user)` followed by `session.permanent = True`, **without** `remember=True`). This is noted explicitly so the contract and implementation agree.

- Nick's earlier "Coordination items for Ryan" bullet that read *"OAuth login: always call `login_user(user, remember=True)`"* is superseded by the resolved §7a.7. Kept as-is in Nick's implementation-notes section above for historical accuracy; the authoritative spec is §7a.7 as edited.

- §7a.13 originally required missing `GITHUB_OAUTH_*` env to fail at startup with no exception; implementation and CI need `TESTING=1` runs without a GitHub app (backdoor e2e). §7a.13 Errors now split production (fail on import) vs `TESTING=1` (OAuth optional; `/login/github` flashes to `/login`). Ryan PR #18.

### Pushback / decisions deliberately deferred to a later week

- No multi-provider auto-link by email this week (study guide §3 default).
- No display of GitHub `name` or `email` in the UI for Week 7 (only `username` rendered).
- No Alembic migration ? Nick's PR documents the operational `docker compose down -v` requirement for the first deploy in §7a.11.
- No real-GitHub assertion in CI Playwright ? the test-login backdoor stands in. The manual GitHub smoke gets one named entry in `team_walkthrough.md` (Part 3).

### Outstanding work tracked

- **Liam**: rebase `week7-client-oauth-ux` on latest `main` before merge so `e2e/whole_system.md` is not accidentally deleted by the merge.
- **Ryan**: implement the server slice (Authlib, `/login/github`, `/auth/github/callback`, create/link, `/test/login/<username>`) on `week7-server-oauth`; write one Playwright test in `tests/e2e/`; write `role_work.md`.
- **All three**: Part 3 `tests/e2e/test_full_lifecycle.py` (4 scenarios) and `team_walkthrough.md` after individual slices land.
