# Week 10 — Server-side final notes (Ryan Belmonte)

Team: **Cache Kings**
Role: **Server-side**
Repo: [TCSS506-CacheKings/Trail-checker](https://github.com/TCSS506-CacheKings/Trail-checker)

This document records my server-side ownership, what I built, what I reviewed at capstone integration, and known limitations. It complements [`CONTRACTS.md`](../CONTRACTS.md), [`role_work.md`](../role_work.md) (Week 7), and [`e2e/server.md`](../e2e/server.md).

---

## 1. Server-side scope

I own Flask route handlers, external API integration (OpenWeather), recommendation logic, JSON/HTML response contracts, production runtime integration (gunicorn + ProxyFix behind nginx), and GitHub OAuth server paths.

Primary files:

| Area | Files |
|------|--------|
| Routes & auth | `app.py` |
| External API / domain logic | `weather_service.py` |
| Contracts | `CONTRACTS.md` (§4 routes, §5 server-side boundary, §7a OAuth) |
| Server-side tests | `tests/test_server_conditions.py`, `tests/test_integration.py`, OAuth-related coverage in `tests/test_auth.py` |
| Production runtime | `gunicorn.conf.py`, `Dockerfile` (gunicorn CMD), ProxyFix in `app.py` |
| Week 6 e2e walk | `e2e/server.md` |

I do **not** own final CSS/visual layout (Liam) or schema/security policy design (Nick), though I coordinate on anything that touches auth, sessions, or route contracts.

---

## 2. Work timeline (traceable on GitHub)

| Phase | Deliverable | Evidence |
|-------|-------------|----------|
| Week 6 | OpenWeather integration, `/api/conditions`, `/trail-checker/results`, `weather_service.py` | PR #6, #10, #11; `tests/test_server_conditions.py` |
| Week 7 | GitHub OAuth routes, test backdoor, e2e server OAuth test, contract gap-fill | PR #17, #18, #24; `role_work.md` Ryan section |
| Week 8 | gunicorn + ProxyFix behind nginx | PR #27; merged via hardening → main (#30) |
| Week 10 capstone | Public deploy (EC2); **server-side review** of integration PR #34 | PR #34 review comment (Ryan, 2026-06-10); this file |

Shared EC2/Cursor sessions sometimes commit as `Ubuntu`; co-authored trailers on some commits link team members. My named merges and feature PRs above are the primary server-side authorship trail.

---

## 3. Routes and behavior I originally built

### Conditions / external API

- **`GET /api/conditions`** — JSON envelope (`ok` / `data` / `error`), OpenWeather geocode + weather + air pollution via `weather_service.py`
- **`GET /trail-checker/results`** — HTML results; partial failure handling; persists `trail_checks` on success
- **`weather_service.py`** — timeouts, status handling, recommendation (`good` / `caution` / `poor` / `unknown`)

### Auth (Week 7)

- **`GET /login/github`**, **`GET /auth/github/callback`** — Authlib OAuth; transactional create/link; redirect to saved trails
- **`GET /test/login/<username>`** — test-only backdoor (`TESTING=1`; 404 in production)
- Startup guard: OAuth env required outside `TESTING`

### Production (Week 8)

- **gunicorn** on port 8000; **ProxyFix** so Flask sees HTTPS and correct host behind nginx
- Deployed stack: **nginx → gunicorn → Flask → Postgres** (Docker Compose)

---

## 4. Capstone integration (PR #34) — reviewed, not reverted

PR #34 (`site-visuals-level-2`) added UX and layout work. Several changes touch **server-side** behavior. I reviewed them explicitly on the PR before approval.

### Routes / helpers added or changed (integration)

| Piece | Purpose |
|-------|---------|
| `GET /` | Home is trail checker (was separate home + `/trail-checker`) |
| `GET /trail-checker` | Legacy redirect to `/` |
| `GET /login/save-location` | Queue location in session; redirect to login; auto-save after auth |
| `_safe_next_url`, `_post_login_redirect_url`, `_redirect_after_auth` | Safe post-login redirects (password, register, OAuth) |
| `_save_trail_for_user`, `_consume_pending_saved_trail` | Shared save logic + login-to-save flow |
| `POST /saved-trails/<id>/recheck` | JSON recheck for in-page updates (`static/js/saved_trails.js`) |
| `_get_owned_saved_trail` | Ownership check before recheck/delete |
| `_claim_anonymous_trail_checks` | Attach anonymous `trail_checks` to user on save (MVP tradeoff) |

### What I verified in review

- Input validation on login-to-save and saved-trail mutations
- `_safe_next_url` blocks open redirects (relative paths only)
- Saved-trail writes scoped by `user_id`
- Recheck uses stored coordinates (`get_conditions_for_coordinates`), not geocode bypass
- JSON errors on `/recheck` match shared envelope
- `CONTRACTS.md` updated; tests in `tests/test_auth.py` and `tests/test_server_conditions.py`
- CI green on PR branch

**Verdict:** Integration work in my lane, acceptable for capstone. I did not revert; I reviewed and approved with documented tradeoffs.

---

## 5. Architecture boundaries

```text
Browser
  → nginx (TLS, rate limits, attack-path blocks, security headers)
  → gunicorn
  → Flask app.py (routes, auth, session, HTML/JSON responses)
       → weather_service.py (OpenWeather, recommendation — swappable service layer)
       → SQLModel / Postgres (persistence — Nick’s schema; queries enforce ownership in routes)
```

- **Contracts:** Frontend and backend integrate through documented routes and JSON shapes in `CONTRACTS.md`, not ad hoc coupling.
- **`app.py` size:** The file is large (~1.3k lines after capstone). Acceptable for this course timeline; a future refactor would split auth, saved-trails, and trail-checker into blueprints or modules without changing contracts.
- **Extensibility:** New features should touch `weather_service.py` or a single route module + contract update + tests — pattern established in Weeks 6–7.

---

## 6. Known limitations (honest)

| Limitation | Impact | Notes |
|------------|--------|--------|
| `_claim_anonymous_trail_checks` | Anonymous checks linked by lat/long only | Documented in CONTRACTS §8; production would use session/token binding |
| Self-signed TLS on public IP | Browser warning; OAuth callback fragile | Live URL uses HTTPS but cert is `CN=localhost`; domain + Let’s Encrypt would be the upgrade |
| `create_all` schema | No Alembic migrations | First deploy / schema changes may need `docker compose down -v` (see README) |
| E2e tests use SQLite | CI e2e ≠ production Postgres | Production Postgres verified manually — see `e2e/server.md` §7 |
| `/test/login/` | Must stay 404 in production | Verified on live deploy |

---

## 7. Production verification

Live deployment (capstone): **https://34.219.236.117/**

Server-side smoke checks I expect before submission:

- `GET /` — trail checker loads
- `GET /api/conditions?q=Seattle` — JSON `ok: true` with weather + air quality
- `GET /trail-checker/results?q=…` — HTML results with live OpenWeather
- Register / login / logout — session and redirects
- Saved trail create + `POST .../recheck` — JSON update (authenticated)
- `GET /test/login/alice` — **404** in production

Detailed steps and pass criteria: **`e2e/server.md` §7** (capstone production verification, 2026-06-10).

---

## 8. How to run server-side tests

```bash
TESTING=1 SECRET_KEY=test-secret pytest -v --ignore=tests/e2e -m "not integration"
```

Playwright (auth lifecycle, includes server OAuth backdoor path):

```bash
TESTING=1 SECRET_KEY=test-secret-e2e pytest -v tests/e2e
```

With Docker stack on localhost:

```bash
pytest tests/test_attack_paths.py -v -m integration
```

---

## 9. Related PR review

Full server-side review comment on **PR #34** (GitHub, Ryan Belmonte, 2026-06-10): routes/helpers reviewed, tradeoffs accepted, comfortable approving from server-side lane.
