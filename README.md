# Trail Conditions Checker

## Team name, members, and roles

Team: Cache Kings

Members:

* Ryan Belmonte — Server-side
* Liam Sipp — Client-side
* Nick Stjern — DB-and-security

Since our team has three members, we shared coordinator responsibilities across the group. Ryan focused on Flask routes, external API integration, server-side logic, OAuth/server behavior, and backend flow. Liam focused on JavaScript, CSS, browser interactivity, templates, visual presentation, user-flow testing, and demo-path verification. Nick focused on schema design, persistence, input validation, security hardening, nginx behavior, and production-stack/deployment concerns.

## Project

Trail Conditions Checker is a Flask/Postgres web application that helps hikers, trail runners, cyclists, and other outdoor users check current conditions before heading out.

The app combines location search, current weather, air quality, saved locations, and a simple recommendation into one unified trail conditions view. The goal is to be more than a basic weather app: Trail Checker presents current condition data in a clear outdoor-focused workflow so users can quickly decide whether a location seems reasonable to visit.

## The user

Our user is a hiker, trail runner, cyclist, or outdoor enthusiast who wants to check current conditions before choosing a trail, park, mountain, city, or outdoor destination. Their goal is to quickly answer whether a location seems reasonable to visit today based on weather, air quality, wind, visibility, and overall condition signals.

## Delivered MVP

The final delivered version lets users search for an outdoor location, view current conditions, and save locations for later.

Core delivered features:

* Search for a trailhead, city, park, mountain, or outdoor location
* Fetch current weather for the searched location
* Fetch current air quality information
* Display weather, air quality, location details, and a recommendation in one unified results view
* Allow users to register and log in with a regular username/password flow
* Support GitHub OAuth login when production OAuth credentials are configured
* Allow logged-in users to save locations
* View saved trails/locations
* Re-check current conditions for saved locations
* Delete saved locations
* Persist users, OAuth identities, saved trails, and trail condition checks in Postgres
* Run through the Week 8 production stack: nginx, gunicorn, Flask, Postgres, and Docker Compose

## Live deployment

Final deployed application:

https://34.219.236.117/

The final deployed app is served from an EC2 instance and is reachable over HTTPS using the Week 8 production stack.

## Architecture

The production request path is:

Browser → nginx → gunicorn → Flask → Postgres

* nginx terminates HTTPS, serves static assets, applies security headers, rate-limits selected auth routes, and proxies application requests to gunicorn.
* gunicorn runs the Flask app as the production WSGI server.
* Flask handles routes, authentication, search/results, saved trails, and external API integration.
* Postgres stores users, OAuth identities, saved trails, and trail check data.
* OpenWeather provides geocoding, current weather, and air pollution/air quality data.
* Secrets such as `SECRET_KEY`, `OPENWEATHER_API_KEY`, and GitHub OAuth credentials are loaded from environment variables and are not committed to the repository.

## External APIs

The delivered version uses OpenWeather for:

* Geocoding a searched location into coordinates
* Current weather data
* Air pollution / air quality data

The app requires an `OPENWEATHER_API_KEY` environment variable. The key is not committed to the repository.

Earlier project planning considered additional services such as AirNow and OpenStreetMap/Nominatim. The final implementation uses OpenWeather as the primary external data source so the app can keep the condition lookup flow focused and deployable within the course timeline.

## Final integration note

During final integration, some UI polish crossed the original role boundaries so the team could ship a stronger final product. Liam reviewed the final client-side user flow, tested the visual branch locally, verified register/login/logout behavior, ran the main test suite, and handled final UX/demo-path validation. Nick contributed late visual polish while also maintaining DB/security and deployment responsibilities.

## Why this project

We chose this project because it gives each team member a clear technical area while still forcing us to work together on integration. The server-side work involves coordinating external API data and handling failure cases. The client-side work involves presenting mixed condition data clearly to a real user. The database/security work involves user data, saved trails, input validation, secret hygiene, and production-stack hardening.

This project also gives us practice with real production concerns: API keys, rate limits, fallback behavior, partial failures, persistent state, authentication, Docker, nginx, gunicorn, and Postgres. Those skills transfer well to many types of software projects, including backend systems, platform engineering, data tools, and public-facing web apps.

## Documentation

Team project docs:

- [`docs/Week10_Server_Side_Final_Notes.md`](docs/Week10_Server_Side_Final_Notes.md) — Ryan (server-side): ownership, capstone integration review, architecture boundaries, and known limitations
- [`CONTRACTS.md`](CONTRACTS.md) — route and API contracts
- [`role_work.md`](role_work.md) — Week 7 per-role contributions
- [`e2e/server.md`](e2e/server.md) — server-side end-to-end verification walkthrough

## Running the production stack locally

nginx terminates TLS and proxies to gunicorn on the internal Docker network. Postgres is not published to the host, which keeps the database behind the Docker network boundary.

1. Copy `.env.example` to `.env`.

2. Set required secrets and configuration values:

```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql://app:app@db:5432/app
OPENWEATHER_API_KEY=replace-with-real-openweather-key
OAUTH_CLIENT_ID=replace-with-real-github-client-id
OAUTH_CLIENT_SECRET=replace-with-real-github-client-secret
```

3. For local GitHub OAuth testing, register the local callback URL:

```text
https://localhost/auth/github/callback
```

For deployed GitHub OAuth testing, the callback URL must match the deployed public URL.

4. Generate a self-signed cert for local HTTPS:

```bash
mkdir -p nginx/certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout nginx/certs/key.pem -out nginx/certs/cert.pem \
  -days 365 -subj "/CN=localhost"
```

5. Start the stack:

```bash
docker compose up --build -d
```

6. Open:

```text
https://localhost
```

Accept the browser warning for the self-signed local certificate.

## Required environment variables

| Variable              | Required                      | Notes                                                                         |
| --------------------- | ----------------------------- | ----------------------------------------------------------------------------- |
| `SECRET_KEY`          | Yes                           | The app refuses to boot outside debug/testing if this is left at the default. |
| `DATABASE_URL`        | Yes                           | Defaults to the Compose Postgres URL.                                         |
| `OPENWEATHER_API_KEY` | Yes for live condition search | Used for OpenWeather geocoding, weather, and air quality data.                |
| `OAUTH_CLIENT_ID`     | Yes for GitHub OAuth          | Must match a real GitHub OAuth app.                                           |
| `OAUTH_CLIENT_SECRET` | Yes for GitHub OAuth          | Must match a real GitHub OAuth app.                                           |
| `TESTING`             | Tests only                    | Used by test configuration.                                                   |

## Running tests

The repository includes automated tests for authentication, templates, database/security behavior, integration flow, and server condition routes.

The production Docker image intentionally excludes the `tests/` folder through `.dockerignore`, so running this inside the app container will collect zero tests:

```bash
docker compose exec app pytest -v
```

To run the main test suite from the Docker environment, mount the local tests folder into the app container.

Windows PowerShell:

```powershell
docker compose run --rm -v "${PWD}\tests:/app/tests:ro" app pytest -v tests/test_auth.py tests/test_client_templates.py tests/test_db_security.py tests/test_integration.py tests/test_server_conditions.py
```

Verified local result after final merge:

```text
52 passed, 1 warning
```

## Attack-path test

With the stack running, the nginx attack-path test can be run with:

```bash
pytest tests/test_attack_paths.py -v -m integration
```

This verifies that known bad paths are handled at the nginx edge rather than being treated as normal app traffic.

## Resetting the database

The app uses `SQLModel.metadata.create_all` for first-run schema creation. This does not alter existing tables when constraints change.

When schema changes land, reset the Postgres volume:

```bash
docker compose down -v
docker compose up -d
```

Skipping `-v` will keep the previous schema and may prevent new constraints from being enforced.

## Final verification

Local final `main` verification:

* `main` pulled cleanly
* Docker image rebuilt from `main`
* nginx/app/db containers healthy
* `/` returns 200
* `/trail-checker` redirects to `/`
* `/login` returns 200
* `/register` returns 200

Live EC2 verification:

* Public homepage loads
* Search works
* Results load
* Register/login works
* Save location works
* Saved Trails page works
* Re-check conditions works
* Delete saved trail works
* Logout works

## Known limitations

* Local GitHub OAuth requires a real GitHub OAuth app and matching callback URL. Placeholder OAuth credentials will not work.
* A newly created OpenWeather API key may return 401 until it activates.
* The local HTTPS certificate is self-signed, so browsers show a warning on `https://localhost`.
* The production Docker image intentionally excludes tests; tests should be run from the repository or mounted into the test container.
* Trail Checker provides current condition guidance, not professional safety advice. Users should still check official trail, road, wildfire, and weather sources before outdoor travel.
