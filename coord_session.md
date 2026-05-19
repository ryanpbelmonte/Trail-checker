# Week 6 Coordinator / Planning Session

Team: Cache Kings  
Project: Trail Checker  
Repo: https://github.com/TCSS506-CacheKings/Trail-checker

## Participants

- Liam Sipp — Client-side
- Ryan Belmonte — Server-side
- Nick Stjern — DB-and-security

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
