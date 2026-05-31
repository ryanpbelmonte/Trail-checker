# Trail Conditions Checker

## Team name, members, and roles

Team: Cache Kings

Members:
- Ryan Belmonte - Server-side
- Liam Sipp - Client-side
- Nick Stjern - Db-and-security

Since our team has three members, we will share coordinator responsibilities across the group. Ryan will focus on Flask routes, external API integration, server-side logic, and templates. Liam will focus on JavaScript, CSS, browser interactivity, and presentation. Nick will focus on schema design, migrations, input validation, indexes, and secret hygiene.

## Project

We are starting with a custom Trail Conditions Checker project. The app will combine multiple data sources, including weather, air quality, and location data, into one unified trail conditions view.

The goal is to build more than a basic weather app. We want to practice integrating multiple APIs with different schemas, rate limits, and failure cases while presenting the results clearly to the user.

## The user

Our user is a hiker, trail runner, cyclist, or outdoor enthusiast who wants to check current conditions before choosing a trail. Their goal is to quickly answer whether a trail seems reasonable to visit today based on weather, air quality, and basic trail/location information.

## MVP

Version 1 will let a user choose from a predefined list of trails and view current conditions for that trail. The system will fetch current weather, air quality, and location data, then combine those results into a single conditions dashboard.

Core MVP features:
- Select a trail from a predefined list of test trails
- Fetch current weather for the selected trail
- Fetch current air quality information for the selected trail
- Display trail/location information in one unified view
- Cache API responses to reduce unnecessary requests
- Show partial results if one external API fails instead of failing the entire page

Features outside the MVP:
- User accounts
- Saved favorite trails
- Notifications or alerts
- Historical condition trends
- Full map visualization

## External APIs

Our first API choices are OpenWeather for weather conditions, AirNow for air quality information, and OpenStreetMap/Nominatim for location search or geocoding support. OpenWeather requires an API key, AirNow requires a public API account, and Nominatim has strict usage expectations, including a low request rate and caching requirements.

Our backup plan is to reduce external API use by storing a small predefined trail list with coordinates directly in our database. If one API is unavailable or too limited, the app can still show manually stored trail information and any available condition data from the remaining APIs.

## Why this project

We chose this project because it gives each team member a clear technical area while still forcing us to work together on integration. The server-side work involves coordinating several external APIs, the client-side work involves presenting mixed data clearly, and the database/security work involves storing trail data, validating inputs, protecting API keys, and designing basic caching.

This project also gives us practice with real production concerns: rate limits, API keys, fallback behavior, partial failures, and clean data presentation. Those skills transfer well to many types of software projects, including backend systems, platform engineering, data tools, and public-facing web apps.

## Running the production stack (Week 8)

nginx terminates TLS and proxies to gunicorn on the internal Docker network.
Postgres is not published to the host (§13 trust boundary).

1. Copy `.env.example` to `.env` and set secrets (`SECRET_KEY`, `OPENWEATHER_API_KEY`, GitHub OAuth).
2. Register GitHub OAuth callback: `https://localhost/auth/github/callback`
3. Generate a self-signed cert (one-time, not committed):

```bash
mkdir -p nginx/certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout nginx/certs/key.pem -out nginx/certs/cert.pem \
  -days 365 -subj "/CN=localhost"
```

4. Start the stack:

```bash
docker compose up --build -d
```

5. Open **https://localhost** (accept the browser warning for the self-signed cert).

### Attack-path test (nginx edge, §10)

With the stack running:

```bash
pytest tests/test_attack_paths.py -v -m integration
```

## Resetting the database

The app uses `SQLModel.metadata.create_all` for first-run schema creation. This does not alter existing tables when constraints change.

When schema changes land (new columns, new constraints, FK cascade behavior, unique constraints), reset the Postgres volume:

```bash
docker compose down -v
docker compose up -d
```

Skipping `-v` will silently keep the previous schema and the new constraints will not be enforced.

## Required environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `SECRET_KEY` | Yes (non-debug) | The app refuses to boot outside of debug/testing if this is left at the default. |
| `DATABASE_URL` | Yes | Defaults to the Compose Postgres URL. |
| `OPENWEATHER_API_KEY` | Server-side slice | Never hardcode; read only from environment. |
| `TESTING` | Tests only | Set to `1` to disable CSRF and the login rate limiter during pytest runs. `tests/conftest.py` sets this automatically. |

## Running tests

Unit and integration tests (no Docker stack required):

```bash
TESTING=1 SECRET_KEY=test-secret pytest -v --ignore=tests/e2e -m "not integration"
```

Playwright e2e tests:

```bash
TESTING=1 SECRET_KEY=test-secret-e2e pytest -v tests/e2e
```
