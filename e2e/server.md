# E2E Walk — Server-side slice

**Role:** Ryan Belmonte (server-side)
**Team:** Cache Kings
**Scope:** OpenWeather integration and conditions routes — `/api/conditions`, `/trail-checker/results` — against a running Flask app (not pytest).

## 1. Definition

End-to-end for the server-side slice means: a real HTTP client hits the **deployed Flask app**, which calls **live OpenWeather** (geocoding, current weather, air pollution), and returns JSON or HTML that matches `CONTRACTS.md`. Boundaries exercised: **HTTP client → Flask routes → `weather_service.py` → OpenWeather APIs**. Postgres and saved-trail flows are out of scope for this slice (Nick/Liam + follow-up routes).

This walk intentionally uses **Python `requests`** inside the app container (same discipline as curl; the slim Docker image has no `curl` installed).

## 2. The walk

### Setup

**Step 1.** From repo root, ensure dependencies and env are configured:

```bash
cp .env.example .env
# Edit .env and set OPENWEATHER_API_KEY=your-key-here

docker compose up -d
```

**Step 2.** Confirm the Trail Checker app is the process on port 5000 (not another project). Hit a route only this repo implements:

```bash
docker compose exec app python -c "import requests; print(requests.get('http://127.0.0.1:5000/trail-checker').status_code)"
```

Expect `200`. If `404`, the wrong app may be bound to port 5000 on the host.

### JSON API (`/api/conditions`)

**Step 3.** Invalid input — short query:

```bash
docker compose exec app python -c "
import requests, json
r = requests.get('http://127.0.0.1:5000/api/conditions', params={'q': 'M'})
print(r.status_code, json.dumps(r.json()))
"
```

**Step 4.** Happy path — realistic outdoor location ( **must use real OpenWeather** ):

```bash
docker compose exec app python -c "
import requests, json
r = requests.get('http://127.0.0.1:5000/api/conditions', params={'q': 'Mount Rainier'})
print(r.status_code)
data = r.json()
print('ok:', data.get('ok'))
if data.get('ok'):
    d = data['data']
    print('resolved:', d.get('resolved_name'))
    print('weather keys:', list(d.get('weather', {}).keys()))
    print('aqi:', d.get('air_quality', {}).get('aqi'))
    print('recommendation:', d.get('recommendation'))
else:
    print(json.dumps(data, indent=2))
"
```

**Step 5.** Not found — nonsense location (real geocoder, empty or no match):

```bash
docker compose exec app python -c "
import requests, json
r = requests.get('http://127.0.0.1:5000/api/conditions', params={'q': 'zzzznotrealplace999'})
print(r.status_code, json.dumps(r.json()))
"
```

**Step 6.** Edge query — truthy-fixture check (pick something odd):

```bash
docker compose exec app python -c "
import requests, json
r = requests.get('http://127.0.0.1:5000/api/conditions', params={'q': 'Rainier'})
print(r.status_code)
print(json.dumps(r.json(), indent=2)[:800])
"
```

Document whether the first geocoding result is reasonable for hikers.

**Step 7.** Missing API key (error path):

```bash
docker compose run --rm --no-deps -e OPENWEATHER_API_KEY= app python -c "
import subprocess, time, requests, json
p = subprocess.Popen(['python', 'app.py'])
time.sleep(4)
r = requests.get('http://127.0.0.1:5000/api/conditions', params={'q': 'Mount Rainier'})
print(r.status_code, json.dumps(r.json()))
p.terminate()
"
```

Expect `503` / `external_api_unavailable`.

### HTML route (`/trail-checker/results`)

**Step 8.** Results page with real query (browser or requests):

```bash
docker compose exec app python -c "
import requests
r = requests.get('http://127.0.0.1:5000/trail-checker/results', params={'q': 'Mount Rainier'})
print('status', r.status_code)
print('weather-card', 'data-testid=\"weather-card\"' in r.text)
print('recommendation-badge', 'data-testid=\"recommendation-badge\"' in r.text)
"
```

With a valid API key, expect `200` and both `data-testid` markers present.

## 3. Pass criteria

- **Step 1:** `.env` contains `OPENWEATHER_API_KEY`; `docker compose up` succeeds.
- **Step 2:** `/trail-checker` returns `200` from the Trail Checker app.
- **Step 3:** Status `400`, JSON `ok: false`, `error.code == "invalid_input"`.
- **Step 4:** Status `200`, `ok: true`, `data.weather`, `data.air_quality`, and `data.recommendation` present; resolved name and coordinates look like Mount Rainier area (not empty or unrelated continent).
- **Step 5:** Status `404`, `error.code == "not_found"` (when API key is set and geocoder returns no results).
- **Step 6:** Response documented honestly — if ambiguous geocode result, note as finding.
- **Step 7:** Status `503`, `error.code == "external_api_unavailable"`.
- **Step 8:** Status `200`; HTML includes `data-testid="weather-card"` and `data-testid="recommendation-badge"`.

## 4. Execution log

Run date: 2026-05-21 (initial), **2026-05-21 re-run after key activation**
Environment: EC2, Docker Compose, in-container `requests` via isolated `trail-checker-e2e-app` container (host port 5000 occupied by Week 5 assignment `week_5_506-app-1`; Trail Checker uses internal port 5000 only)

| Step | Result | Notes |
|------|--------|-------|
| 1 | PASS | `.env` contains a 32-character `OPENWEATHER_API_KEY`; key accepted by OpenWeather after activation window |
| 2 | PASS | `GET /trail-checker` → `200` |
| 3 | PASS | `400`, `invalid_input` for `q=M` |
| 4 | PASS | `200`, `ok: true`, `resolved_name: Mount Rainier`, `recommendation: caution`, `aqi: 3`. **Note:** geocoder returned lat/lon `38.94, -76.96` (Mid-Atlantic US), not WA Mount Rainier — see Finding 3 |
| 5 | PASS | `404`, `not_found` for `zzzznotrealplace999` |
| 6 | PASS | `200`, `q=Rainier` resolved to `Rainier, WA area` (`46.09, -122.94`) — different from step 4; see Finding 3 |
| 7 | PASS | (2026-05-20 prior run) Empty `OPENWEATHER_API_KEY` → `503` with clear message |
| 8 | PASS | `200`; `data-testid="weather-card"` and `data-testid="recommendation-badge"` present in HTML |

### Finding 1 — New OpenWeather account: dashboard shows Active, API still returns 401 (resolved)

**Symptom:** Initial run (~15 min after account creation): steps 4–6 returned `503` / OpenWeather **401 Invalid API key** even though the dashboard showed **Active**.

**Root cause:** OpenWeather [FAQ](https://openweathermap.org/faq#error401) — new API keys can take 10 minutes to 2 hours to activate after signup.

**Resolution:** Re-run after ~1 hour — geocode probe returned **200**, steps 4–6 and 8 **PASS** with live weather data.

**Lesson:** A non-empty `.env` entry and an **Active** dashboard status are not enough on day one — e2e must confirm the upstream accepts the key (step 4 is the truthy-fixture check).

### Finding 2 — Host port 5000 may not be Trail Checker

**Symptom:** `curl localhost:5000/api/conditions` on the host returned Flask 404 HTML (route not registered).

**Root cause:** Another process or older app bound to port 5000, or Compose app not running.

**Fix:** Use `docker compose up -d` for this repo, or verify with `/trail-checker` before e2e.

**Lesson:** E2E setup step should confirm app identity, not assume port 5000.

### Finding 3 — Ambiguous geocoding: "Mount Rainier" vs "Rainier"

**Symptom:** Step 4 (`q=Mount Rainier`) and step 6 (`q=Rainier`) both returned `200` but resolved to **different coordinates**.

**Data:**
- `Mount Rainier` → `38.94, -76.96` (Mid-Atlantic US, not the Washington volcano)
- `Rainier` → `46.09, -122.94` (Pacific Northwest, closer to the expected trailhead)

**Root cause:** Contract MVP uses the **first geocoding result** with no disambiguation UI (`CONTRACTS.md` §8).

**Fix:** Not required for Week 6. Future improvement: let users pick among geocoding matches, or prefer outdoor/trail-related result types.

**Lesson:** Live e2e caught a real product gap that mocked tests with fixed fixtures would miss — short or ambiguous place names may not resolve to the hiker's intended location.

## 5. Re-run checklist

Live OpenWeather steps completed 2026-05-21 after key activation. If re-running later:

1. Recreate the e2e app container so it reloads `.env`:
   ```bash
   docker rm -f trail-checker-e2e-app
   docker compose run -d --name trail-checker-e2e-app -e SECRET_KEY=e2e-test-secret-not-default app python app.py
   ```
2. Confirm geocode probe returns **200** before steps 4–8
3. Re-run steps 4, 5, 6, 8 from §2

**Note:** If host port 5000 is occupied (e.g. by a Week 5 assignment container), use the isolated `trail-checker-e2e-app` container above — it exercises internal port 5000 without conflicting on the host.

## 6. Per-role note

This file is the **server-side** contribution to the team `e2e.md`. Coordinator should link or merge sections from Liam (browser UI), Nick (Postgres/auth), and this doc for the whole-system walk.

## 7. Capstone production verification

**Run date:** 2026-06-10
**Environment:** Live EC2 deploy at **https://34.219.236.117/** — nginx → gunicorn → Flask → Postgres (Week 8 Docker stack). TLS is self-signed (`CN=localhost`).
**Scope:** Server-side routes and live OpenWeather on production. Full authenticated flows (register, save, recheck, delete, logout) are covered in the team browser checklist in `README.md` §Final verification; this section records what Ryan verified from the server-side lane with `curl` against the public URL.

### 7.1 Setup

Confirm the deploy responds over HTTPS and is the Trail Checker app (not a stale branch):

```bash
BASE="https://34.219.236.117"
curl -skI "$BASE/" | head -3
curl -skI "$BASE/trail-checker" | rg -i "HTTP/|location:"
curl -skI "$BASE/test/login/alice" | head -1
```

Expect: `/` → `200`; `/trail-checker` → `302` to `/`; `/test/login/alice` → `404` (production must not expose the test backdoor).

### 7.2 JSON API on production

```bash
# Invalid input
curl -sk "$BASE/api/conditions?q=M"

# Happy path — live OpenWeather (required)
curl -sk "$BASE/api/conditions?q=Seattle" | python3 -m json.tool | head -30
```

### 7.3 HTML results on production

```bash
curl -sk "$BASE/trail-checker/results?q=Seattle" | python3 -c "
import sys
t = sys.stdin.read()
print('weather-card', 'data-testid=\"weather-card\"' in t)
print('recommendation-badge', 'data-testid=\"recommendation-badge\"' in t)
"
```

### 7.4 Auth gate (unauthenticated)

```bash
curl -skI "$BASE/saved-trails" | rg -i "HTTP/|location:"
curl -skL -o /dev/null -w "login_page=%{http_code}\n" "$BASE/login"
curl -skL -o /dev/null -w "register_page=%{http_code}\n" "$BASE/register"
```

Expect: unauthenticated `GET /saved-trails` → `302` to `/login?next=%2Fsaved-trails`; login and register pages → `200` after redirect chain.

### 7.5 Pass criteria

| Check | Expected |
|-------|----------|
| HTTPS homepage | `200`, `server: nginx` |
| `/trail-checker` | `302` → `/` |
| `/test/login/alice` | `404` |
| `GET /api/conditions?q=M` | `400`, `invalid_input` |
| `GET /api/conditions?q=Seattle` | `200`, `ok: true`, weather + air_quality + recommendation |
| `GET /trail-checker/results?q=Seattle` | `200`, weather-card + recommendation-badge testids |
| `GET /saved-trails` (no session) | `302` → login with `next=` |
| `GET /login`, `GET /register` | `200` (follow redirects) |

Authenticated save / recheck / delete / logout: see `README.md` §Final verification (browser walk — Liam verified on deploy branch before merge to `main`).

### 7.6 Execution log (2026-06-10)

| Step | Result | Notes |
|------|--------|-------|
| 7.1 HTTPS + identity | **PASS** | `/` `200`; nginx/1.27.5; `/trail-checker` → `/` |
| 7.1 test backdoor | **PASS** | `GET /test/login/alice` → `404` |
| 7.2 invalid API | **PASS** | `400`, `invalid_input` for `q=M` |
| 7.2 live OpenWeather | **PASS** | `q=Seattle` → `ok: true`, `resolved_name: Seattle`, `recommendation: good`, `aqi: 2` |
| 7.3 HTML results | **PASS** | `200`; both `data-testid` markers present; title `Trail Checker — Seattle` |
| 7.4 auth gate | **PASS** | `/saved-trails` → `/login?next=%2Fsaved-trails`; login/register pages `200` |
| Auth POST via curl | **SKIP** | nginx `limit_req` on `/login` and `/register` (`5r/m`) returns `503` under rapid automated POST bursts; CSRF session pairing needs a real browser — use README browser checklist instead |

### 7.7 Findings

**Finding 4 — nginx auth rate limit vs automated curl**

`nginx/nginx.conf` applies `limit_req zone=auth` (`5r/m`, burst 3) to `/login` and `/register`. Rapid repeated `POST` from one IP during e2e scripting can return **503** from nginx before Flask runs. This is expected hardening, not an app bug. Browser users and spaced manual checks are unaffected.

**Finding 5 — Self-signed TLS on public IP**

Certificate subject is `CN=localhost`. Browsers show a warning on first visit to `https://34.219.236.117/`. The deployment uses HTTPS through nginx as required by the Week 8 stack, but the certificate is self-signed, so browsers warn on the public IP. A real domain + Let's Encrypt would remove the warning.

**Finding 6 — Ambiguous geocoding (unchanged from Week 6)**

Production still returns the first OpenWeather geocode match (`CONTRACTS.md` §8). Short or ambiguous names may not resolve to the hiker’s intended trailhead — same lesson as Finding 3 in §4.

### 7.8 Re-run checklist

Before final submission, from any machine with network access to the live URL:

1. Run §7.1–7.4 commands against `https://34.219.236.117/`.
2. Confirm step 7.2 happy path returns live weather (not `503` / `external_api_unavailable`).
3. Complete authenticated flows in a browser per `README.md` §Final verification.
4. Space auth-route checks if you hit nginx `503` on `/login` or `/register` POST.
