# E2E walk - DB-and-security slice

**Role:** DB-and-security (Nick)
**Scope:** Schema constraints in deployed Postgres, Flask-Login refactor, and ownership rules.

## Definition

End-to-end for this slice means: the deployed Postgres container enforces the
constraints from `CONTRACTS.md` at the database level (not just the ORM), and a
real browser session honors Flask-Login's auth and ownership rules across
`/saved-trails` flows.

## Walk

1. **Start a clean stack.** `docker compose down -v && docker compose up -d`.
2. **Inspect schema in Postgres.** `docker compose exec db psql -U app -d app -c "\d users" -c "\d saved_trails" -c "\d trail_checks"`.
3. **Probe NOT NULL on `saved_trails.user_id`.** From the same `psql`, run an INSERT that omits `user_id`.
4. **Probe FK on `saved_trails.user_id`.** Insert a row with `user_id = 999999` (no such user).
5. **Probe duplicate prevention at the DB layer.** Register `e2e_dbsec_dup_<ts>` via the UI, capture its id with `SELECT id FROM users WHERE username = 'e2e_dbsec_dup_<ts>';`, then run two identical `INSERT INTO saved_trails (user_id, display_name, query_text, latitude, longitude, created_at, updated_at) VALUES (<id>, 'Mount Rainier', 'Mount Rainier', 46.8523, -121.7603, NOW(), NOW());` statements directly in `psql`. Then repeat the duplicate-save attempt via the UI as a separate app-layer check.
6. **Probe ON DELETE CASCADE on a namespaced test user.** Register `e2e_dbsec_cascade_<ts>` via the UI, capture its id, save one trail via the UI, then `DELETE FROM users WHERE id = <captured id>;` and re-query `saved_trails WHERE user_id = <captured id>`. Never delete by username pattern or by ad-hoc id - always by the id you just captured.
7. **Auth refactor sanity in browser.** Register -> log in -> open dev tools -> confirm the Flask session cookie payload contains `_user_id` and `_fresh` -> log out -> confirm those keys are gone.
8. **Login-required enforcement.** While logged out, hit `GET /saved-trails`, `POST /saved-trails`, `POST /saved-trails/<id>/delete`, `GET /saved-trails/<id>/check`.
9. **Ownership probe (two users).** As user A save a trail (note its id). Log out, log in as user B, hit `POST /saved-trails/<A's id>/delete` and `GET /saved-trails/<A's id>/check` directly.
10. **Secret hygiene check (presence only, never print the value).** Run `docker compose exec app python -c "import os; print('OPENWEATHER_API_KEY:', 'set' if os.getenv('OPENWEATHER_API_KEY') else 'missing')"` and `git grep -nE "OPENWEATHER_API_KEY|appid=|api.openweathermap.org"`. Do not run `env | grep` or otherwise dump the value into shell history, screenshots, or the execution log.

## Pass criteria

1. Both containers reach healthy state; `app` logs show no startup errors.
2. Column types, `NOT NULL`, `UNIQUE`, and `REFERENCES ... ON DELETE CASCADE` lines match the schema section of `CONTRACTS.md` exactly. A screenshot of `\d saved_trails` goes in the log.
3. Postgres rejects the INSERT with `null value in column "user_id" violates not-null constraint`. Not a Python exception - a DB-side error.
4. Postgres rejects with `violates foreign key constraint`. Verified at the DB layer, not by SQLModel.
5. The second direct `INSERT` is rejected by Postgres with `duplicate key value violates unique constraint`. If that error does not fire, the contract's "no exact duplicates per user" rule is not actually enforced by the database - file a contract gap and fix it by adding a `UniqueConstraint(user_id, latitude, longitude)` to the SQLModel. The UI attempt may additionally be caught at the app layer, but app-layer enforcement alone does not satisfy this step.
6. After deleting the captured user id, `SELECT COUNT(*) FROM saved_trails WHERE user_id = <captured id>;` returns `0`. Cascade verified at the DB, not by app code.
7. After login, the session cookie payload contains `_user_id` and `_fresh`. After logout those keys are gone. Flask sessions are signed but not encrypted, so the payload is base64-decodable in dev tools.
8. Every anonymous request returns `302` to `/login` (or `401` for JSON). No 500s, no partial renders that leak data.
9. Both endpoints return `404`, not `403`, and the response body does not reveal whether trail id `<A's id>` exists.
10. The presence check prints `set`. `git grep` finds `OPENWEATHER_API_KEY` only in code that reads `os.environ`, never as a hardcoded literal, and finds no `appid=<actual key>` strings. The execution log records "set" / "no hardcoded value found" - never the key itself.

## Execution log

1. [ ] 
2. [ ] Paste `\d` output or screenshot.
3. [ ] Paste exact Postgres error.
4. [ ] Paste exact Postgres error.
5. [ ] Record whether the second direct INSERT was rejected by Postgres or accepted (gap).
6. [ ] Record row counts before and after; record captured user id.
7. [ ] Record cookie keys observed in dev tools before and after logout.
8. [ ] Record status codes for each endpoint.
9. [ ] Confirm 404 vs 403; note any info leak.
10. [ ] Record "set" / "missing" and grep summary only. Never paste the key.

**Findings & fixes:** Replace with real observations; link commit SHAs for any fix. Honest "step 5: Postgres accepted the duplicate - added `UniqueConstraint` in <sha>" is worth more than ten green checkmarks.
