# E2E walk - Client-side slice

**Role:** Client-side (Liam)  
**Branch:** client/trail-checker-templates  
**Scope:** Flask-rendered Trail Checker pages, Bootstrap layout, navigation, forms, stable test selectors, and browser-visible behavior.

## Definition

End-to-end for the client-side slice means verifying that a real user can navigate the Flask-rendered Trail Checker interface in a browser and interact with the forms and pages described in `CONTRACTS.md`.

For this slice, the browser is the main boundary. The client-side work does not own OpenWeather API calls, database schema, saved-trail persistence, Flask-Login, or ownership enforcement. Those belong to the server-side and DB/security roles. The client-side slice owns the rendered templates, Bootstrap presentation, form field names, navigation links, empty states, and stable selectors used by the client-side tests.

The full end-to-end system is browser -> Flask routes -> Postgres -> OpenWeather. My slice focuses on whether the browser-facing templates correctly consume those routes and expose the correct forms, links, and visible states once the backend pieces are available.

## Walk

### Setup

1. **Start from the client-side branch.**  
   Run `git checkout client/trail-checker-templates`.

2. **Verify local working tree is clean.**  
   Run `git status`.

3. **Run the client-side test file.**  
   Run `py -m pytest tests/test_client_templates.py -v`.

### Anonymous user flow

4. **Open the Trail Checker page.**  
   In a browser, open `/trail-checker`.

5. **Verify the search page renders.**  
   Confirm the page has a clear Trail Checker heading, explanation text, and a search form.

6. **Verify the search form contract.**  
   Inspect the form and confirm:
   - `method="GET"`
   - `action="/trail-checker/results"`
   - input name is `q`
   - submit button is visible

7. **Verify navbar access.**  
   From the home page, confirm the navbar includes a visible Trail Checker link pointing to `/trail-checker`.

### Results page flow

8. **Submit a realistic search.**  
   Search for `Mount Rainier`.

9. **Verify results layout.**  
   Confirm the results page shows:
   - resolved location name
   - query text
   - weather card
   - air quality card
   - recommendation badge
   - search-again link

10. **Verify stable test selectors.**  
    Inspect the rendered HTML and confirm:
    - `data-testid="weather-card"`
    - `data-testid="air-quality-card"`
    - `data-testid="recommendation-badge"`

11. **Verify logged-out save prompt.**  
    While logged out, confirm the page shows a message prompting the user to log in before saving a location.

### Logged-in / saved-trails flow

12. **Log in or register.**  
    Register a test user or log in with an existing test user.

13. **Return to a Trail Checker result.**  
    Search for `Mount Rainier` again while logged in.

14. **Verify save form appears.**  
    Confirm the save form posts to `/saved-trails` and includes:
    - `csrf_token`
    - `display_name`
    - `query_text`
    - `latitude`
    - `longitude`
    - optional `country`
    - optional `state`

15. **Open the saved trails page.**  
    Open `/saved-trails`.

16. **Verify saved-trails empty state or card list.**  
    If no trails are saved, confirm `data-testid="saved-trails-empty"` is present. If trails exist, confirm each saved trail appears as a card with a re-check link and delete form.

17. **Verify delete form contract.**  
    Confirm each delete form posts to `/saved-trails/<id>/delete` and includes a `csrf_token`.

### Browser quality check

18. **Check browser console.**  
    Open DevTools and verify there are no JavaScript errors caused by the client-side templates.

19. **Check responsive layout quickly.**  
    Resize the browser to a narrow width and confirm the cards/forms remain usable.

## Pass criteria

- **Step 1:** The branch is `client/trail-checker-templates`.
- **Step 2:** `git status` reports a clean working tree.
- **Step 3:** Client-side tests pass, except for failures caused by backend routes not yet available on the base branch.
- **Step 4:** `/trail-checker` returns a rendered page, not a 404.
- **Step 5:** The search page is readable and Bootstrap-styled.
- **Step 6:** The form contract exactly matches `CONTRACTS.md` and the client-side tests.
- **Step 7:** Navbar includes `href="/trail-checker"`.
- **Step 8:** The search submits through the agreed GET route.
- **Step 9:** Results page presents weather, air quality, and recommendation sections clearly.
- **Step 10:** Required `data-testid` selectors are present and unchanged.
- **Step 11:** Logged-out users are clearly told to log in before saving.
- **Step 12:** Login/register flow works using the shared auth system.
- **Step 13:** Logged-in users can return to the Trail Checker result page.
- **Step 14:** Save form includes all agreed hidden fields and CSRF token.
- **Step 15:** `/saved-trails` is reachable once the DB/security and server-side saved-trail routes are integrated.
- **Step 16:** Saved trails page shows either the empty state or saved trail cards.
- **Step 17:** Delete forms include the correct route and CSRF token.
- **Step 18:** Browser console has no client-side template-related errors.
- **Step 19:** Layout remains usable on a narrow viewport.

## Execution log

| Step | Result | Notes |
|------|--------|-------|
| 1 | PASS | Branch `client/trail-checker-templates` was created and pushed. |
| 2 | PASS | Working tree was clean before CSRF follow-up work; later CSRF changes were committed and pushed. |
| 3 | PARTIAL PASS | `py -m pytest tests/test_client_templates.py -v` produced 3 passing tests and 1 expected failure. |
| 4 | PASS | `/trail-checker` route exists on Ryan's server-side base branch. |
| 5 | PASS | Search page was polished with Bootstrap card layout and helper sections. |
| 6 | PASS | Search form keeps `method="GET"`, `action="/trail-checker/results"`, and input `name="q"`. |
| 7 | PASS | Added `href="/trail-checker"` to `templates/base.html`. |
| 8 | PASS WITH MOCKS | Results-page client test uses mocked OpenWeather responses so CI does not need a real API key. |
| 9 | PASS | Results template includes separate weather, air quality, and recommendation sections. |
| 10 | PASS | Required selectors were preserved: `weather-card`, `air-quality-card`, and `recommendation-badge`. |
| 11 | PASS | Logged-out result page includes a login prompt. |
| 12 | NOT RUN YET | Full browser login check waits for DB/security branch integration. |
| 13 | NOT RUN YET | Full logged-in result flow waits for DB/security and saved-trail route integration. |
| 14 | PASS BY TEMPLATE REVIEW | Save form includes required hidden fields and was updated to include `csrf_token`. |
| 15 | BLOCKED | `/saved-trails` currently returns 404 on Ryan's base branch because saved-trail routes are not present there yet. |
| 16 | PASS BY TEMPLATE REVIEW / BLOCKED IN ROUTE | `templates/saved_trails.html` includes `data-testid="saved-trails-empty"`, but route verification waits for backend integration. |
| 17 | PASS BY TEMPLATE REVIEW | Delete form posts to `/saved-trails/{{ trail.id }}/delete` and includes `csrf_token`. |
| 18 | NOT RUN YET | Browser console check will be completed after role branches are integrated. |
| 19 | NOT RUN YET | Responsive browser check will be completed after role branches are integrated. |

## Findings and fixes

### Finding 1 - Results page client test needed mocked OpenWeather responses

**Symptom:** The client-side results-page test would fail in CI because `/trail-checker/results` depends on OpenWeather data and CI does not have a real API key.

**Root cause:** The original client-side test hit the real route without mocking the external API boundary.

**Fix:** Updated `tests/test_client_templates.py` with `@responses.activate` and mocked OpenWeather geocoding, current weather, and air pollution responses.

**Lesson:** Even a client-side structural test can cross into server/external-service behavior when the template is rendered through a real Flask route. Mocking the external API keeps the test focused on the client-side selectors and layout.

### Finding 2 - Saved trails page cannot be fully verified until backend route exists

**Symptom:** `test_saved_trails_page_has_empty_state` currently fails because `/saved-trails` returns 404 on Ryan's base branch.

**Root cause:** `templates/saved_trails.html` exists in the client-side branch, but the `/saved-trails` route is owned by the DB/security and server-side integration work and is not present on the current base branch.

**Fix:** No client-side code fix needed yet. The template includes the required `data-testid="saved-trails-empty"`. Once Nick's DB/security work and Ryan's saved-trail routes are integrated, rerun the client-side test.

**Lesson:** This is a true integration dependency. The client-side template can be correct while the route remains unavailable until another role's slice lands.

### Finding 3 - CSRF requirement added by DB/security slice

**Symptom:** Nick's DB/security branch added CSRF protection for state-changing POST routes.

**Root cause:** Save and delete forms in the client-side templates are POST forms, so they must include CSRF tokens.

**Fix:** Added `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` to the save form in `trail_results.html` and the delete form in `saved_trails.html`.

**Lesson:** Security changes often require template updates. Client-side forms need to stay aligned with DB/security requirements, not just server route names.

## Remaining client-side work

- Re-run `py -m pytest tests/test_client_templates.py -v` after Nick's DB/security branch and Ryan's saved-trail routes are integrated.
- Browser-test `/saved-trails` once the route exists.
- Complete execution log steps 12, 13, 15, 16, 18, and 19.
- Update this file with final PASS/FAIL observations before final submission.
