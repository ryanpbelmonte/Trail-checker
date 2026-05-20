# E2E walk - Client-side slice

**Role:** Client-side (Liam)  
**Branch:** client/trail-checker-templates, now merged into main  
**Scope:** Flask-rendered Trail Checker pages, Bootstrap layout, navigation, forms, stable test selectors, CSRF-compatible POST forms, and browser-visible behavior.

## Definition

End-to-end for the client-side slice means verifying that a real user can navigate the Flask-rendered Trail Checker interface and interact with the pages and forms described in `CONTRACTS.md`.

For this slice, the browser is the main boundary. The client-side work does not own OpenWeather API calls, database schema, saved-trail persistence, Flask-Login, or ownership enforcement. Those belong to the server-side and DB/security roles. The client-side slice owns the rendered templates, Bootstrap presentation, form field names, navigation links, empty states, CSRF-compatible POST form markup, and stable selectors used by the client-side tests.

The full end-to-end system is browser -> Flask routes -> Postgres -> OpenWeather. My slice focuses on whether the browser-facing templates correctly consume those routes and expose the correct forms, links, and visible states once the backend pieces are available.

## Walk

### Setup

1. **Start from main after role PRs are merged.**  
   Run `git checkout main` and `git pull`.

2. **Verify local working tree is clean.**  
   Run `git status`.

3. **Run the full test suite.**  
   Run `py -m pytest -v`.

4. **Run the client-side test file specifically.**  
   Run `py -m pytest tests/test_client_templates.py -v`.

### Anonymous user flow

5. **Open the Trail Checker page.**  
   In a browser, open `/trail-checker`.

6. **Verify the search page renders.**  
   Confirm the page has a clear Trail Checker heading, explanation text, and a search form.

7. **Verify the search form contract.**  
   Inspect the form and confirm:
   - `method="GET"`
   - `action="/trail-checker/results"`
   - input name is `q`
   - submit button is visible

8. **Verify navbar access.**  
   From the home page, confirm the navbar includes a visible Trail Checker link pointing to `/trail-checker`.

### Results page flow

9. **Submit a realistic search.**  
   Search for `Mount Rainier`.

10. **Verify results layout.**  
    Confirm the results page shows:
    - resolved location name
    - query text
    - weather card
    - air quality card
    - recommendation badge
    - search-again link

11. **Verify stable test selectors.**  
    Inspect the rendered HTML and confirm:
    - `data-testid="weather-card"`
    - `data-testid="air-quality-card"`
    - `data-testid="recommendation-badge"`

12. **Verify logged-out save prompt.**  
    While logged out, confirm the page shows a message prompting the user to log in before saving a location.

### Logged-in / saved-trails flow

13. **Log in or register.**  
    Register a test user or log in with an existing test user.

14. **Return to a Trail Checker result.**  
    Search for `Mount Rainier` again while logged in.

15. **Verify save form appears.**  
    Confirm the save form posts to `/saved-trails` and includes:
    - `csrf_token`
    - `display_name`
    - `query_text`
    - `latitude`
    - `longitude`
    - optional `country`
    - optional `state`

16. **Open the saved trails page.**  
    Open `/saved-trails`.

17. **Verify saved-trails empty state or card list.**  
    If no trails are saved, confirm `data-testid="saved-trails-empty"` is present. If trails exist, confirm each saved trail appears as a card with a re-check link and delete form.

18. **Verify delete form contract.**  
    Confirm each delete form posts to `/saved-trails/<id>/delete` and includes a `csrf_token`.

### Browser quality check

19. **Check browser console.**  
    Open DevTools and verify there are no JavaScript errors caused by the client-side templates.

20. **Check responsive layout quickly.**  
    Resize the browser to a narrow width and confirm the cards/forms remain usable.

## Pass criteria

- **Step 1:** Branch is `main` and includes merged role PRs.
- **Step 2:** `git status` reports a clean working tree.
- **Step 3:** Full test suite passes.
- **Step 4:** Client-side test file passes.
- **Step 5:** `/trail-checker` returns a rendered page, not a 404.
- **Step 6:** The search page is readable and Bootstrap-styled.
- **Step 7:** The form contract exactly matches `CONTRACTS.md` and the client-side tests.
- **Step 8:** Navbar includes `href="/trail-checker"`.
- **Step 9:** The search submits through the agreed GET route.
- **Step 10:** Results page presents weather, air quality, and recommendation sections clearly.
- **Step 11:** Required `data-testid` selectors are present and unchanged.
- **Step 12:** Logged-out users are clearly told to log in before saving.
- **Step 13:** Login/register flow works using the shared auth system.
- **Step 14:** Logged-in users can return to the Trail Checker result page.
- **Step 15:** Save form includes all agreed hidden fields and CSRF token.
- **Step 16:** `/saved-trails` is reachable.
- **Step 17:** Saved trails page shows either the empty state or saved trail cards.
- **Step 18:** Delete forms include the correct route and CSRF token.
- **Step 19:** Browser console has no client-side template-related errors.
- **Step 20:** Layout remains usable on a narrow viewport.

## Execution log

| Step | Result | Notes |
|------|--------|-------|
| 1 | PASS | Role PRs were merged into `main`. |
| 2 | PASS | `git status` on `main` reported a clean working tree. |
| 3 | PASS | `py -m pytest -v` passed: 23 passed in 1.75s. |
| 4 | PASS | Client-side tests are included in the full passing suite. |
| 5 | PASS BY TEST / BROWSER CHECK PENDING | `/trail-checker` route is covered by passing client-side tests. |
| 6 | PASS BY TEMPLATE REVIEW | Search page was polished with Bootstrap card layout and helper sections. |
| 7 | PASS | Search form keeps `method="GET"`, `action="/trail-checker/results"`, and input `name="q"`. |
| 8 | PASS | Added `href="/trail-checker"` to `templates/base.html`; client-side navbar test passes. |
| 9 | PASS WITH MOCKS | Results-page client test uses mocked OpenWeather responses so CI does not need a real API key. |
| 10 | PASS | Results template includes separate weather, air quality, and recommendation sections. |
| 11 | PASS | Required selectors were preserved: `weather-card`, `air-quality-card`, and `recommendation-badge`. |
| 12 | PASS BY TEMPLATE REVIEW | Logged-out result page includes a login prompt. |
| 13 | PASS BY INTEGRATION TEST | Register/login flow is covered by passing auth and integration tests. |
| 14 | PASS BY INTEGRATION TEST | Logged-in search flow is covered by passing integration test. |
| 15 | PASS BY TEMPLATE REVIEW | Save form includes required hidden fields and `csrf_token`. |
| 16 | PASS | `/saved-trails` route is now integrated and the saved-trails client-side test passes. |
| 17 | PASS | `templates/saved_trails.html` includes `data-testid="saved-trails-empty"` and saved trail card markup. |
| 18 | PASS BY TEMPLATE REVIEW | Delete form posts to `/saved-trails/{{ trail.id }}/delete` and includes `csrf_token`. |
| 19 | NOT RUN YET | Browser console check still needs to be completed against the running app. |
| 20 | NOT RUN YET | Responsive browser check still needs to be completed against the running app. |

## Findings and fixes

### Finding 1 - Results page client test needed mocked OpenWeather responses

**Symptom:** The client-side results-page test would fail in CI because `/trail-checker/results` depends on OpenWeather data and CI does not have a real API key.

**Root cause:** The original client-side test hit the real route without mocking the external API boundary.

**Fix:** Updated `tests/test_client_templates.py` with `@responses.activate` and mocked OpenWeather geocoding, current weather, and air pollution responses.

**Lesson:** Even a client-side structural test can cross into server/external-service behavior when the template is rendered through a real Flask route. Mocking the external API keeps the test focused on the client-side selectors and layout.

### Finding 2 - Saved trails route dependency resolved after integration

**Symptom:** Earlier, `test_saved_trails_page_has_empty_state` failed because `/saved-trails` returned 404 on Ryan's base branch.

**Root cause:** `templates/saved_trails.html` existed in the client-side branch, but the `/saved-trails` route depended on DB/security and server-side integration.

**Fix:** After Nick's DB/security work, Ryan's server-side work, and my client-side work were merged into `main`, the saved trails route was available and the full test suite passed.

**Lesson:** This was a real integration dependency. The client-side template was correct before the route existed, but the end-to-end behavior could only pass once all role slices were merged.

### Finding 3 - CSRF requirement added by DB/security slice

**Symptom:** Nick's DB/security branch added CSRF protection for state-changing POST routes.

**Root cause:** Save and delete forms in the client-side templates are POST forms, so they must include CSRF tokens.

**Fix:** Added `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` to the save form in `trail_results.html` and the delete form in `saved_trails.html`.

**Lesson:** Security changes often require template updates. Client-side forms need to stay aligned with DB/security requirements, not just server route names.

## Remaining client-side work

- Run the app in a browser.
- Complete the browser console check.
- Complete the quick responsive layout check.
- Update steps 19 and 20 from `NOT RUN YET` to final observations before submission, if time allows.
