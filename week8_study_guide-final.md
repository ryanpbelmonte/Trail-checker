# Week 8 Study Guide — Production Stack and Hardening

This is the reference material for Week 8\. The assignment points you to specific sections by number — read the section, paste relevant config into your LLM, adapt to your project.

Read it section by section. Don't try to absorb it all at once.

---

## Part I — The Production Stack: What and Why

### §1. The whole picture

A request to your production app travels through five distinct pieces of software, in this order:

Browser  →  nginx  →  gunicorn  →  Flask  →  Postgres

   HTTPS     :443      WSGI       your code    SQL

Each piece does something the others can't or shouldn't.

**Browser** sends an HTTPS request to your domain on port 443\. It expects a valid TLS certificate, security headers in the response, and a session cookie if the user is logged in.

**nginx** terminates TLS — the certificate decryption happens here, not anywhere downstream. nginx also serves static assets directly (CSS, JS, images), enforces rate limits on sensitive endpoints, applies security headers to every response, and filters obviously malicious traffic before it ever reaches your Python code. Critically, nginx talks to gunicorn over plain HTTP via a unix socket or local TCP port — both processes live on the same host, so the un-encrypted hop is fine.

**gunicorn** is the WSGI server. It manages a pool of worker processes, hands each incoming HTTP request to a worker, and the worker invokes your Flask app. gunicorn does no application logic of its own — it's the bridge between HTTP and Python.

**Flask** is your application code. Routes, models, business logic. The same Flask app you've been writing all term — but now it runs under gunicorn, not `flask run`.

**Postgres** stores your data. Reachable from Flask via a docker network, not exposed to the public internet. The trust boundary is the docker network itself.

The pieces compose into one logical unit via `docker-compose.yml`. Three containers, one network, one running stack.

### §2. Why `flask run` isn't a production server

The Flask documentation says outright: do not use the development server in production. Three reasons:

**Single-threaded by default.** `flask run` handles one request at a time. Your second concurrent user waits for your first to finish. On a slow endpoint with a few users, your app feels broken even though nothing is.

**Debug mode leaks tracebacks.** When `debug=True`, Werkzeug's interactive debugger activates on uncaught exceptions. Anyone who triggers an exception sees a full Python traceback and an interactive shell in their browser — including database credentials, secret keys, and any other context the exception captured. If `debug=True` ever escapes to a public IP, you've effectively published a remote code execution endpoint.

**No graceful reload under load.** When you push a new version, `flask run` doesn't drain in-flight requests or restart workers atomically. Connections drop. State is lost. There's no way to do a zero-downtime deploy.

gunicorn fixes all three: a pool of worker processes handles many requests concurrently, no debug shell is ever exposed, and worker restarts can be staged so requests in flight finish before the worker dies.

### §3. The WSGI contract

WSGI — Web Server Gateway Interface — is a Python standard (PEP 3333\) that specifies how HTTP servers and Python web frameworks talk to each other. It's just a function signature:

def application(environ, start\_response):

    \# environ is a dict of request data

    \# start\_response is a callback for sending status \+ headers

    \# returns an iterable of response body bytes

Flask conforms to this contract. The Flask app object is callable with `(environ, start_response)` — that's what makes it "a WSGI app." gunicorn implements the other side: it knows how to invoke any object that conforms to this signature.

Why this matters beyond gunicorn: WSGI is the *contract* that lets you swap servers. If you ever moved off gunicorn — to uWSGI, mod\_wsgi, or Waitress — your Flask code doesn't change. The contract is the seam.

ASGI is the newer async version of this idea. FastAPI uses it. The pattern is the same — a function signature acts as a portable contract — just with `async` semantics for streaming and long-lived connections.

The lesson generalizes: well-defined contracts at infrastructure boundaries make every layer independently swappable. WSGI is one example. The Docker image format is another. HTTP itself is another.

---

## Part II — The Configs (Canonical Versions)

### §4. nginx.conf — annotated

This is the canonical nginx config for the stack. Adapt it to your project — domain name, paths, and any project-specific routes.

\# Define the upstream — where nginx forwards proxied requests.

upstream app {

    server unix:/tmp/gunicorn.sock;

    \# or: server gunicorn:8000;  if using docker-compose TCP networking

}

\# Rate limiting zone for auth endpoints (10 MB of state, 5 req/min per IP)

limit\_req\_zone $binary\_remote\_addr zone=login:10m rate=5r/m;

server {

    listen 443 ssl http2;

    server\_name yourapp.example.com;

    \# TLS configuration

    ssl\_certificate     /etc/nginx/certs/cert.pem;

    ssl\_certificate\_key /etc/nginx/certs/key.pem;

    ssl\_protocols TLSv1.2 TLSv1.3;

    ssl\_prefer\_server\_ciphers off;

    \# Security headers — applied to every response

    add\_header Strict-Transport-Security "max-age=31536000" always;

    add\_header X-Frame-Options "DENY" always;

    add\_header X-Content-Type-Options "nosniff" always;

    add\_header Referrer-Policy "strict-origin-when-cross-origin" always;

    add\_header Content-Security-Policy "default-src 'self'" always;

    \# Static assets served directly by nginx

    location /static/ {

        alias /app/static/;

        expires 30d;

    }

    \# Login endpoint with rate limiting

    location /login {

        limit\_req zone=login burst=3 nodelay;

        proxy\_pass http://app;

        include proxy\_params.conf;

    }

    \# Everything else proxied to gunicorn

    location / {

        proxy\_pass http://app;

        proxy\_set\_header Host              $host;

        proxy\_set\_header X-Real-IP         $remote\_addr;

        proxy\_set\_header X-Forwarded-For   $proxy\_add\_x\_forwarded\_for;

        proxy\_set\_header X-Forwarded-Proto $scheme;

    }

}

\# Redirect plain HTTP to HTTPS

server {

    listen 80;

    server\_name yourapp.example.com;

    return 301 https://$host$request\_uri;

}

The load-bearing directives:

- `upstream` defines the backend. Unix socket is faster and uses file permissions for access control; TCP is easier to debug.  
- `ssl_protocols TLSv1.2 TLSv1.3` excludes obsolete and broken TLS versions. No TLS 1.0, no TLS 1.1, no SSLv3.  
- `X-Forwarded-Proto $scheme` is the header that tells Flask the original request came in over HTTPS. Without this, Flask thinks the connection is plain HTTP (because nginx talks plain HTTP to it), and `SESSION_COOKIE_SECURE=True` will refuse to set cookies.  
- `limit_req` enforces the rate-limiting zone defined at the top. `burst=3 nodelay` allows short bursts (a user mistyping their password a few times) but blocks sustained attacks.  
- The HTTP-to-HTTPS redirect at the bottom catches anyone who navigates to your site by typing the bare domain — they get bounced to HTTPS instead of getting "site unreachable."

### §5. gunicorn.conf.py — annotated

\# gunicorn.conf.py — production config for the WSGI server

\# Where gunicorn listens. Unix socket for nginx on the same host.

bind \= "unix:/tmp/gunicorn.sock"

\# Alternative for docker-compose with TCP:

\# bind \= "0.0.0.0:8000"

\# Number of worker processes. Rule of thumb: (2 \* CPU cores) \+ 1\.

\# Adjust based on actual load measurement.

workers \= 3

\# Worker class. sync is the default and right for most apps.

\# Use gthread for I/O-bound apps doing slow external calls.

\# Use gevent only if you've thought hard about monkey-patching.

worker\_class \= "sync"

\# Per-worker request timeout. Kills hung workers.

timeout \= 30

\# How long to let in-flight requests finish during a graceful restart.

graceful\_timeout \= 30

\# Logs to stdout/stderr so Docker captures them.

accesslog \= "-"

errorlog  \= "-"

loglevel  \= "info"

\# Restart workers periodically to mitigate any memory leaks.

max\_requests \= 1000

max\_requests\_jitter \= 50

\# Preload the app before forking workers. Faster startup, but means

\# you need to handle DB connections per-worker (don't open them at import time).

preload\_app \= True

Run with:

gunicorn \-c gunicorn.conf.py 'yourapp:create\_app()'

The app-factory pattern (`yourapp:create_app()`) is what gunicorn imports — it calls `create_app()` to get the WSGI callable. If your Flask app is a module-level `app` object instead, use `yourapp:app`.

Worker model decision: start with sync. If you measure that workers spend most of their time waiting on external calls (DB queries, HTTP APIs), switch to gthread with `threads = 4`. gevent is for high-concurrency situations where you've audited every library you use for async safety.

### §6. docker-compose.yml — annotated

\# docker-compose.yml — the three-container production stack

services:

  nginx:

    image: nginx:1.27-alpine

    ports:

      \- "443:443"

      \- "80:80"

    volumes:

      \- ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro

      \- ./nginx/proxy\_params.conf:/etc/nginx/proxy\_params.conf:ro

      \- ./nginx/certs:/etc/nginx/certs:ro

      \- gunicorn-socket:/tmp

      \- ./static:/app/static:ro

    depends\_on:

      \- app

    restart: unless-stopped

  app:

    build:

      context: .

      dockerfile: Dockerfile

    volumes:

      \- gunicorn-socket:/tmp

    environment:

      \- DATABASE\_URL=postgresql://app:app@db:5432/app

      \- SECRET\_KEY=${SECRET\_KEY}

    depends\_on:

      \- db

    restart: unless-stopped

  db:

    image: postgres:16-alpine

    environment:

      \- POSTGRES\_USER=app

      \- POSTGRES\_PASSWORD=app

      \- POSTGRES\_DB=app

    volumes:

      \- postgres-data:/var/lib/postgresql/data

    restart: unless-stopped

    \# Note: db is NOT exposed via 'ports' — it's only reachable from

    \# other services on the docker network. This is the trust boundary.

volumes:

  gunicorn-socket:   \# shared between nginx and app for the unix socket

  postgres-data:     \# persists the database across container restarts

Three things deserve attention:

**The shared `gunicorn-socket` volume.** nginx and the app container both mount it. The app creates the unix socket inside this volume; nginx connects to it from the same volume. Without the shared volume, nginx can't see the socket.

**No `ports:` on the db service.** The database is only reachable from other services on the docker network — `app` can connect to `db:5432` because docker-compose creates a private network, but no port on the host machine is bound to the database. The docker network is the trust boundary.

**Environment variables for secrets.** `SECRET_KEY` is referenced from the shell environment or a `.env` file (gitignored). It's not committed to the repo.

A typical run sequence:

\# Generate a self-signed cert (one-time, not committed)

mkdir \-p nginx/certs

openssl req \-x509 \-newkey rsa:2048 \-nodes \\

  \-keyout nginx/certs/key.pem \-out nginx/certs/cert.pem \\

  \-days 365 \-subj "/CN=localhost"

\# Start the stack

docker-compose up \--build

\# In another terminal, check it's running

docker-compose ps

The container that goes down most often during development is `app` — you change code, the image needs rebuilding. `docker-compose up --build app` rebuilds just that one without restarting the others.

### §7. The Dockerfile and cert generation

\# Dockerfile — for the Flask app container

FROM python:3.12-slim

WORKDIR /app

\# Install Python dependencies first (cached layer)

COPY requirements.txt .

RUN pip install \--no-cache-dir \-r requirements.txt

\# Copy application code

COPY . .

\# Default command — gunicorn with the canonical config

CMD \["gunicorn", "-c", "gunicorn.conf.py", "yourapp:create\_app()"\]

The two-step copy pattern (requirements first, then code) lets Docker cache the pip install layer. If your code changes but requirements.txt doesn't, rebuilding the image is fast — Docker reuses the cached layer with all your dependencies.

**Cert generation.** Self-signed certs are fine for this week. Real certs (Let's Encrypt) are Week 9 work — see §B for the forward-pointer.

The one-liner:

openssl req \-x509 \-newkey rsa:2048 \-nodes \\

  \-keyout nginx/certs/key.pem \\

  \-out nginx/certs/cert.pem \\

  \-days 365 \\

  \-subj "/CN=localhost"

`-x509` makes it a self-signed cert (not a CSR), `-newkey rsa:2048` generates a fresh 2048-bit RSA keypair, `-nodes` skips the passphrase (gunicorn would hang waiting for the prompt otherwise), `-days 365` sets a one-year validity, `-subj "/CN=localhost"` skips the interactive cert info prompt.

**Never commit the cert or key.** Add `nginx/certs/` to `.gitignore`. The cert is regenerated per environment.

---

## Part III — Security Hardening

### §8. nginx as request filter

Most traffic to a public-facing app is bots. They don't know what your app is — they scan for known-vulnerable paths and bail when they don't get a match. Look at any public-facing site's nginx access log for an hour and you'll see hundreds of requests for `/wp-login.php`, `/.env`, `/admin`, `/phpmyadmin/`, `/.git/config`, `/server-status`, `/.aws/credentials`, and dozens of variations on each.

These requests are not for your app. They are for some other app the bot thinks might be running on this IP. The right response is `404 Not Found`, returned in microseconds, with no further processing.

When nginx is in front, this is what happens automatically. nginx doesn't know about `/wp-login.php` either — it's not in any `location` block — so it returns 404\. The request never reaches Flask. Your Flask access log doesn't show it. Your Python process spends zero cycles on it.

Before adding nginx, the same request hits Flask. Flask checks its route table, finds no match, returns 404\. That's also fine — but it took a Python process to do it, your Flask log shows the 404, and during a heavy scan your worker pool is busy handling junk requests instead of real ones.

The shift you should expect after adding nginx:

- Your Flask access log gets dramatically quieter. Real users only.  
- Your nginx access log gets noisier with 404s — but that's nginx returning them, not your app.  
- If a scanner hits `/login` and your login endpoint is rate-limited (Study Guide §12), the scanner gets `503 Service Unavailable` and gives up faster.

This is the request-filter posture: nginx absorbs the noise, Flask only sees signal.

### §9. Security headers

nginx can apply HTTP response headers to every response. The five headers below cover most of the easy hardening wins for a typical Flask app.

**`Strict-Transport-Security: max-age=31536000`** — HSTS. After a browser sees this header on a successful HTTPS response, it refuses to talk to your domain over plain HTTP for the duration of `max-age` (one year in seconds). This blocks downgrade attacks (an attacker on the same network trying to force a user back to HTTP to intercept the session). HSTS only works if every response over HTTPS includes the header — if you forget it on some routes, browsers will fall back to HTTP eventually.

What might break: if you have a `http://` link to your own site anywhere (an old image URL, a manually-typed link in a help page), the browser will rewrite it to `https://` automatically. That's the intended behavior — if your `http://` link doesn't work over HTTPS, fix the link.

**`X-Frame-Options: DENY`** — blocks any other site from putting your app in an `<iframe>`. The attack this prevents is clickjacking: an attacker overlays your login form in an invisible iframe on their site, the user clicks "next" thinking they're on the attacker's site, but they actually clicked your form's submit button.

What might break: if you legitimately want your site to be embedded somewhere (a dashboard widget for partners, say), `DENY` is too strict. Use `SAMEORIGIN` to allow your own subdomains, or `ALLOW-FROM https://partner.com` for specific external embeds. The modern replacement is the `frame-ancestors` directive in CSP, which is more granular.

**`X-Content-Type-Options: nosniff`** — tells the browser to trust the `Content-Type` header on responses and not guess from the file content. The attack this prevents is browsers treating a `.jpg` upload as HTML or JavaScript because the bytes look like HTML, allowing stored XSS via image uploads.

What might break: nothing for most apps. If you intentionally serve files with the wrong `Content-Type` (which is itself a bug), this header will surface that bug as a broken page.

**`Content-Security-Policy: default-src 'self'`** — restricts what URLs the browser will load resources from. With `default-src 'self'`, only resources from your own origin can load — no external CDN scripts, no Google Fonts, no inline JavaScript or styles. This is the strictest possible setting.

What will break: almost certainly your inline `<script>` tags, your inline `<style>` blocks, any CDN-hosted JavaScript, any external fonts, any `onclick=` HTML attributes. CSP is the deepest of the five headers — it deserves its own week of work in any real-world deployment. For now, set it strict, see what breaks, and add specific exceptions (`script-src 'self' https://cdn.jsdelivr.net` for that CDN, etc.) as you discover them.

**`Referrer-Policy: strict-origin-when-cross-origin`** — controls what URL gets sent in the `Referer` header on outbound links. The strict-origin variant sends the full URL on same-origin requests, only the origin (not the path) on cross-origin HTTPS, and nothing on HTTPS→HTTP downgrades. The attack this mitigates is leaking your URLs (which may contain session tokens, user IDs, etc.) to third-party sites the user clicks through to.

What might break: analytics tools that rely on the full Referer URL will see less data. Most modern analytics handle this fine; some older integrations may not.

Set the headers in nginx, not in Flask. Flask never sees the response leave the host — nginx is what the browser actually talks to.

### §10. The script-kiddie attack-path test

This test asserts that your nginx config returns `404` or `403` for known-bad URL paths. The test is `tests/test_attack_paths.py`, and it depends on a JSON fixture `attack_paths.json` of paths to check.

**The test file:**

\# tests/test\_attack\_paths.py

import json

import pytest

import requests

import urllib3

\# Suppress the warning about the self-signed cert in dev

urllib3.disable\_warnings()

with open("attack\_paths.json") as f:

    PATHS \= json.load(f)

BASE \= "https://localhost"

@pytest.mark.parametrize("path", PATHS)

def test\_nginx\_blocks(path):

    """nginx should return 404/403 for known-bad attack paths"""

    r \= requests.get(BASE \+ path, verify=False)

    assert r.status\_code in (404, 403), (

        f"{path} returned {r.status\_code} — nginx let it through"

    )

def test\_flask\_never\_saw\_any\_of\_them():

    """Verify Flask's access log never logged these requests at all"""

    try:

        log\_contents \= open("logs/flask.log").read()

    except FileNotFoundError:

        pytest.skip("flask.log not present (run gunicorn with accesslog=logs/flask.log)")

    for path in PATHS:

        assert path not in log\_contents, f"Flask saw {path} — nginx didn't block it"

**The attack-paths fixture:**

\[

  "/wp-login.php",

  "/wp-admin/",

  "/.env",

  "/.git/config",

  "/.git/HEAD",

  "/.aws/credentials",

  "/.ssh/id\_rsa",

  "/admin/",

  "/administrator/",

  "/phpmyadmin/",

  "/xmlrpc.php",

  "/server-status",

  "/backup.sql",

  "/.htaccess",

  "/config.php",

  "/wp-content/plugins/",

  "/vendor/phpunit/",

  "/.well-known/openid-configuration",

  "/\_profiler/",

  "/actuator/health"

\]

The fixture is 20 paths. Each is a real path that real bots scan for, drawn from public reconnaissance tools like nikto. You can extend it as you discover new patterns in your own logs — every entry is just a string, and the test parametrizes over all of them automatically.

**Running the test:**

\# Bring up the stack

docker-compose up \-d

\# Run pytest

pytest tests/test\_attack\_paths.py \-v

\# You should see 20 PASSED — one per path

**What this test catches:** any change to your nginx config that accidentally routes one of these attack paths to Flask. The most common cause is a too-broad `location /` block without a corresponding deny for known-bad prefixes.

**What this test doesn't catch:** anything that isn't on the list. The path-list approach is a *known-bad-string* test, not a structural security audit. It tells you "these specific 20 paths are blocked." It doesn't tell you "no unauthorized requests reach Flask." See the DB/sec role's strategies conversation and Study Guide §24 for the deeper conversation about what other strategies exist and what each catches.

### §11. Cookie flags activated

In Week 7 you set three cookie flags on your session cookie:

app.config\['SESSION\_COOKIE\_SECURE'\] \= True

app.config\['SESSION\_COOKIE\_HTTPONLY'\] \= True

app.config\['SESSION\_COOKIE\_SAMESITE'\] \= 'Lax'

These flags were *inert* in Week 7 because your dev environment ran on `http://localhost`. The `Secure` flag tells the browser "only send this cookie over HTTPS" — but there was no HTTPS in dev. The browser, recognizing this, refused to set the cookie at all. In Week 7 you tested cookie behavior by temporarily disabling `Secure` for local development.

This week, with HTTPS terminating at nginx and `X-Forwarded-Proto: https` being passed back to Flask (Study Guide §14), the `Secure` flag becomes active. The cookie behavior in dev now matches the cookie behavior in production:

- **`Secure`**: the session cookie is only sent over HTTPS. If anything in your project tries to hit `http://localhost` (not `https://localhost`), the cookie is absent, and the user appears logged out. That's the intended behavior — anyone routing your traffic over HTTP is either misconfigured or attacking you, and they shouldn't see the session.  
    
- **`HttpOnly`**: JavaScript on the page can't read the session cookie via `document.cookie`. This blocks the most common XSS-to-session-hijacking pipeline — an attacker who injects JS into your page still can't steal the cookie and use it elsewhere.  
    
- **`SameSite=Lax`**: the cookie is sent on same-site navigation (clicking a link from elsewhere to your site is fine) but not on cross-site form submissions. This blocks a class of CSRF where an attacker's form auto-submits to your site using the victim's session.

The lesson worth absorbing: a flag that's "set but inert" is a different kind of safety than a flag that's "set and active." Week 7's posture — set the flags, test them with the cookie behavior you can observe — was honest given the constraints. Week 8 is what those flags actually buy you in production.

What might surprise you this week: if your Playwright tests from Week 7 are currently configured against `http://localhost`, they'll start failing the moment the session cookie becomes `Secure`. Either point them at `https://localhost` (with `ignore_https_errors=true` for the self-signed cert) or your tests are no longer exercising the production-like cookie behavior.

### §12. Rate limiting on auth endpoints

The relevant nginx config (also shown in §4):

\# Define the zone (in the http block, before any server block)

limit\_req\_zone $binary\_remote\_addr zone=login:10m rate=5r/m;

\# Use it on the login endpoint (inside your server block)

location /login {

    limit\_req zone=login burst=3 nodelay;

    proxy\_pass http://app;

}

Reading the config: nginx maintains a 10 MB shared-memory zone keyed by client IP address. Each IP can make 5 requests per minute to `/login`. `burst=3` allows a brief burst above this limit (e.g., a user fat-fingering their password and retrying quickly) and `nodelay` means the burst requests aren't queued — they go through immediately, but subsequent requests in the same minute hit the limit.

**What rates make sense for which endpoints:**

- `/login`, `/register`, `/password-reset`: 5 requests per minute is reasonable. A legitimate user logs in a few times per session at most.  
- `/api/*` endpoints used by your frontend: per-endpoint analysis. A search endpoint hit on every keystroke needs a higher rate (or no rate limit) than a state-changing endpoint hit on a button click.  
- Static assets: no rate limit. nginx serves them in microseconds anyway.

**What goes wrong if you set the rate too low:**

Legitimate users get locked out. A user mistyping their password three times in 30 seconds, plus the "I forgot, let me try once more" attempt, is four attempts. With `5r/m` and no `burst`, they're rate-limited. With `5r/m burst=3 nodelay` they're fine.

For per-user rate limiting (rather than per-IP), you need either a session-aware limiter or to write it in Flask — nginx can rate-limit by IP, but it doesn't know about your user identities.

**What goes wrong if you set the rate too high:**

A brute-force attacker can try more passwords per minute. The protection becomes weaker. At 5 requests per minute, an attacker trying a million passwords from one IP takes 138 days — long enough that detection (failed-login alerts) will fire well before they succeed. At 100 requests per minute, the same attack takes 7 days, which is much closer to "fast enough to succeed before detection."

In practice, attackers rotate IPs to evade per-IP rate limits. Rate limiting is one layer; account lockout policies, failed-login monitoring, and CAPTCHAs are others. Don't expect rate limiting alone to prevent credential-stuffing attacks.

### §13. The trust boundary at the docker network

In your `docker-compose.yml` (Study Guide §6), notice that the `db` service has no `ports:` declaration. The `app` service can connect to `db:5432` because docker-compose creates a private network between them — but the database port is not bound to any port on the host machine. From outside docker, the database is unreachable.

This is a trust boundary: the docker network is "inside," everything else is "outside." Containers on the same network can talk to each other freely; nothing outside can reach in except through ports that are explicitly published (in this stack, just nginx on 443).

**What this protects against:**

- Direct database access from the public internet. An attacker scanning your host's IP can't connect to Postgres.  
- Misconfiguration leaks. If a developer accidentally hardcodes a database connection string into client-side code, it won't work from outside the docker network — the attempt is contained.  
- Lateral movement. If something compromises a single container without root access, it still can't reach services that aren't on its network.

**What this does NOT protect against:**

- Anyone with shell access to the host machine. Once you're on the host, you can `docker exec` into any container.  
- SQL injection from your Flask app. The trust boundary stops external connections; it doesn't validate the queries you send from inside.  
- A compromised app container. If an attacker gets code execution in the Flask container, they have the same database access your app does.  
- The container running the database itself. If Postgres has a vulnerability and your container is exploited, the trust boundary doesn't help.

**What's still your responsibility at the DB layer:**

- Parametrized queries. Never construct SQL with string concatenation, even inside the docker network. Your ORM does this for you; if you write raw SQL, use bind parameters.  
- Least-privilege credentials. The DB user your app connects with doesn't need superuser privileges. Create a least-privileged user with only the tables and operations your app actually needs.  
- Backups. The trust boundary doesn't make your data safe from accidental `DROP TABLE` or container loss. Volume snapshots, regular dumps, and tested restore procedures are still required.  
- Encryption at rest. If your host disk is stolen, the trust boundary is meaningless. Disk encryption is the answer there.

The trust boundary is one layer. It's the cheapest layer to add (free, just don't publish the port), and it provides real protection against a real class of threats. It is not a complete defense.

### §14. ProxyFix and `X-Forwarded-Proto`

When nginx terminates TLS and forwards the request to gunicorn over plain HTTP, Flask sees a plain HTTP request. From Flask's perspective:

- `request.scheme` is `'http'`, not `'https'`  
- `request.is_secure` is `False`  
- `url_for()` generates `http://` URLs unless told otherwise  
- `SESSION_COOKIE_SECURE=True` refuses to set the session cookie (because the connection looks insecure)

This is a problem. The user IS on HTTPS — they just happen to be one hop away from the server.

nginx tells Flask the truth via a header:

proxy\_set\_header X-Forwarded-Proto $scheme;

But Flask doesn't trust this header by default. Any HTTP header can be set by anyone — if Flask blindly trusted `X-Forwarded-Proto`, an attacker could send `X-Forwarded-Proto: https` directly and bypass any HTTPS-only logic.

The Werkzeug `ProxyFix` middleware bridges this gap:

from werkzeug.middleware.proxy\_fix import ProxyFix

app \= Flask(\_\_name\_\_)

app.wsgi\_app \= ProxyFix(app.wsgi\_app, x\_for=1, x\_proto=1, x\_host=1, x\_prefix=1)

`ProxyFix` rewrites the WSGI environ before Flask sees it, using `X-Forwarded-*` headers. The numeric arguments (`x_for=1`, etc.) tell ProxyFix to trust *one* proxy in the chain — namely nginx. If your stack added another proxy in front (a load balancer, say), you'd set those to 2\.

After ProxyFix:

- `request.scheme` is `'https'` (read from `X-Forwarded-Proto`)  
- `request.is_secure` is `True`  
- `url_for()` generates `https://` URLs  
- `SESSION_COOKIE_SECURE=True` accepts the request as secure and sets the cookie

**Why this is a Flask concern, not an nginx concern.** nginx is doing its job correctly — TLS terminates at nginx, plain HTTP goes to the backend, the headers are set. The mismatch is in Flask's defaults: Flask assumes it's talking directly to the user. ProxyFix tells Flask "you're actually behind a proxy, here are the headers you should trust."

If you forget ProxyFix, the symptom is "I can't log in." The session cookie gets set in one response (without `Secure`, briefly, while you're debugging), then the next request comes in with `X-Forwarded-Proto: https`, your code checks `request.is_secure` and behaves inconsistently. Login redirects loop. Cookies disappear. Tests fail mysteriously.

Add ProxyFix the moment you put nginx in front of Flask. It's two lines.

---

## Part IV — Deploy Pipeline and Operational Hardening

### §15. Secrets in three places

A secret used by your deploy lives in exactly three places:

1. **Where it's generated.** For a Docker Hub token: Docker Hub → Account → Security → New Access Token. For an EC2 SSH key: `ssh-keygen` on your laptop, public key uploaded to `~/.ssh/authorized_keys` on the EC2 host. For an OAuth client secret: the provider's developer console.  
     
2. **Where it's stored.** For a GitHub Actions workflow: repo Settings → Secrets and variables → Actions → New repository secret. The secret is encrypted at rest and only decrypted in the runner that uses it. For a local dev environment: a gitignored `.env` file.  
     
3. **Where it's used at runtime.** For a Docker Hub login step: `${{ secrets.DOCKERHUB_TOKEN }}` in the workflow YAML. For Flask config: `os.environ['SECRET_KEY']` at app startup.

That's the supply chain. Generated in one place, stored in another, used in a third. Anywhere else the secret appears is a leak.

**What goes wrong if it leaks into a fourth place:**

- **Echoed in a workflow step.** `echo $DOCKERHUB_TOKEN` in a debug command. GitHub Actions tries to redact secrets in log output but the redaction is string-matching — if you base64-encode the secret first and then echo, the encoded form goes through unredacted. Don't echo secrets, ever.  
    
- **Committed to the repo.** A `.env` file accidentally added to a commit. Even if you delete it in a later commit, the secret is in git history. The fix is to rotate the secret immediately — don't try to scrub history; just assume it's compromised the moment it lands in any commit.  
    
- **In an error message.** Your app crashes on startup because a database connection failed. The error message includes the connection string with the embedded password. The error message gets logged to CloudWatch, which is more accessible than your env vars. The password is now in your logs.  
    
- **In an artifact.** Your CI builds a Docker image with the secret baked in as an `ENV` variable. The image gets pushed to a public registry. The secret is now in the image, readable by anyone who can pull the image.

The rule: secrets pass through code, they don't live in code. A reference (`os.environ['KEY']`) is fine; a literal (`SECRET = "xyz..."`) is not.

### §16. Tag-driven releases

Two ways your CI can know it's time to deploy:

**Push-to-deploy.** Every merge to `main` triggers a deploy. The workflow YAML has `on: push: branches: [main]`. Simple, fast, fits the "main is always shippable" discipline. Used by mature teams with excellent test coverage and instant rollback capabilities.

**Tag-driven.** Only an explicit `git tag v0.8.0 && git push --tags` triggers a deploy. The workflow YAML has `on: push: tags: ['v*']`. Deploys are intentional — someone chose to ship by tagging.

For a project like yours: tag-driven is the right answer.

**Argument for tag-driven:**

- Explicit. You know exactly when you deployed and what version.  
- Versioned. Every prod release has a name (`v0.8.0`). If something breaks, you can point at the tag.  
- Auditable. Six months later, "when did we deploy the feature that's now broken?" is answerable by looking at tag history.  
- Rollback is just retagging. `git tag v0.7.0-rollback v0.7.0 && git push --tags` redeploys the previous version.  
- Lower stress. Merging to main doesn't trigger anything irrevocable. Tagging is the irrevocable moment, and it's a separate, intentional action.

**Argument against tag-driven:**

- Slower iteration. Bug fixes don't reach prod until someone tags. For a team running 20 deploys per day, this is friction.  
- Tag discipline required. If the team is loose about tagging, deploys happen at unpredictable times.  
- No automatic rollback. If a tagged deploy is bad, someone has to notice and re-tag the previous version. Push-to-deploy with health checks can roll back automatically.

For a project the size of yours, tag-driven is the lower-risk choice. The friction is real but small; the safety win is real and large. Mature teams switch to push-to-deploy when their test coverage and observability are good enough that they trust every green-on-main commit to be shippable.

### §17. When CI goes red

A GitHub Actions job has just failed at the deploy step. Walk through the diagnostic posture:

**1\. Open the failed run and find the failing step.** Actions UI shows each job and each step with green checkmarks or red Xs. The step that failed is highlighted; click to expand its output.

**2\. Read the log top to bottom of that step.** The error is usually about 80% of the way down — close to the end, but not the absolute end (the end is the exit code line). What you're looking for is the first error message, not the last — many failures cascade, and later errors are downstream of the first.

**3\. Recognize the pattern.** Most CI failures are one of five things:

- **Secret not set.** A reference to `${{ secrets.X }}` expanded to an empty string because X isn't in repo settings. Symptom: auth errors, "permission denied," or commands that silently use a default value.  
- **Wrong runner OS.** Your YAML says `runs-on: ubuntu-latest` but the command you're running needs macOS-specific behavior. Or vice versa. Symptom: command not found, unexpected file paths, shell behaving differently.  
- **Path issues.** A step changes the working directory (`cd somewhere`) and the next step doesn't know that. Actions doesn't preserve cwd between steps by default. Symptom: "no such file or directory" on a file you know exists.  
- **EC2 SSH fails.** The key in `${{ secrets.EC2_SSH_KEY }}` doesn't match the public key in `~/.ssh/authorized_keys` on the host. Symptom: "Permission denied (publickey)."  
- **Docker rate limit.** Docker Hub limits anonymous pulls to 100 per 6 hours per IP. Heavy CI usage exceeds this. Symptom: "toomanyrequests" error on `docker pull`.

**4\. Form a hypothesis.** Based on the pattern, what's most likely? "EC2 SSH fails" → check the SSH key in repo secrets matches the deployed key. "Secret not set" → check repo settings.

**5\. Ask your LLM if you're stuck.** Copy the failing log section. Paste it into the LLM with one sentence of context: "This is a GitHub Actions job failing on the deploy step to AWS EC2. Repo is Flask \+ nginx \+ docker-compose. Here's the log:" The LLM is fast at pattern-matching log output to known failure modes and proposing fixes.

**6\. Don't paste suggested fixes back blindly.** The LLM doesn't know your repo's conventions, your secret names, your deploy target's quirks. Read the suggested change, understand what it does, then apply it. If the LLM suggests a workflow YAML change, read every line — don't just copy-paste over your existing YAML.

**What you would NOT ask the LLM.** Anything that requires repo-specific context the LLM doesn't have: the exact name of your team's deploy bucket, the correct path to your EC2 host, your DNS configuration. These need you, not the LLM. The LLM is for "what does this error mean" and "what's the standard fix." It's not for "what's our deploy target."

**Reproducing locally with `act`.** A tool called `act` runs your Actions workflows locally in Docker. Not a perfect simulation — it doesn't handle macOS runners or some GitHub-specific context — but it catches YAML syntax errors and shell command failures before you push. Install via `brew install act` (mac) or the install script (linux), then `act -W .github/workflows/release.yml`. Worth it when you're iterating on workflow changes.

---

## Part V — The Bigger Picture

### §18. Load balancers

A load balancer is the next box you add when one host isn't enough.

Browser → Load balancer → Host 1 (nginx → gunicorn → Flask)

                       → Host 2 (nginx → gunicorn → Flask)

                       → Host 3 (nginx → gunicorn → Flask)

                                ↓

                            Postgres (shared)

The load balancer accepts incoming traffic on port 443 and distributes it across many copies of your application stack. Each copy runs on its own host. A single nginx instance can handle thousands of requests per second on modest hardware — but a single host can fail, and a single host limits your total capacity.

**What an LB adds that nginx doesn't:**

- **Horizontal scaling.** When one host can't handle the traffic, you add another host instead of upgrading the existing one. The LB spreads load across all hosts.  
- **Health checks.** The LB periodically pings each backend host. If a host stops responding, the LB stops routing traffic to it until it recovers. nginx alone can't do this — nginx in front of gunicorn is one process; it doesn't know there's a second gunicorn elsewhere.  
- **Zero-downtime deploys.** With multiple hosts, you can drain traffic from one, upgrade it, return it to rotation, then move to the next. Users never see downtime. With one host, every deploy is a blip.

**What an LB is:** AWS Application Load Balancer, AWS Network Load Balancer, GCP Load Balancer, HAProxy, Traefik. Even nginx can be configured as a load balancer (the `upstream` block with multiple `server` lines). The conceptual layer is "fan traffic out to many backends"; the implementation can be many things.

**The new single point of failure.** With a load balancer in front, the LB itself becomes the single thing that, if it fails, takes everything down. In a serious deployment, the LB is also replicated — multiple LB instances behind a DNS round-robin, or anycast routing. Past that, you're into territory beyond this course.

**Forward-pointer: Kubernetes.** A Kubernetes cluster is mostly this picture, automated. Pods (your app containers) get scheduled across nodes (your hosts). A Service object acts as the load balancer in front of pods. The orchestration handles health checks, restarts, deploys, and scaling. You don't need it for a small project, but the mental model — replicas behind a load balancer, all stateless, with a separate stateful database tier — is the same picture as on this slide.

### §19. The single point of failure

In your current setup, multiple things could fail and take everything down. There's no single SPOF — there are several. Identifying them is the start of designing resilience.

**The database.** If Postgres goes down, your app's read-write paths break instantly. Even with multiple app hosts, every one of them depends on the same database. The remediation is replication — a primary-replica setup where reads can hit replicas and writes go to the primary; if the primary fails, a replica is promoted.

**The single nginx instance.** If your one nginx process crashes, no traffic reaches gunicorn. The remediation is multiple nginx instances behind a load balancer (Study Guide §18), or running nginx with a process supervisor (systemd, docker's `restart: unless-stopped`) so it auto-restarts.

**The host itself.** Power loss, hardware failure, network partition, the cloud provider rebooting the instance — your single host is the single thing all the containers run on. The remediation is multiple hosts.

**The docker daemon.** If docker itself stops on your host, all your containers stop. The remediation is monitoring the daemon and either restarting it or failing over to another host.

**The container registry.** Your deploy pulls images from Docker Hub. If Docker Hub is down or rate-limits you, deploys fail. The remediation is a private registry (AWS ECR, GCP Container Registry) or a pull-through cache.

**The DNS provider.** If your DNS provider goes down, users can't resolve `yourapp.com`. The remediation is multiple DNS providers (rare for small projects), or just choosing a reliable provider.

**The TLS certificate.** Self-signed certs don't expire silently, but Let's Encrypt certs expire every 90 days. If your renewal automation breaks, your cert expires and the site goes down. The remediation is monitoring renewal success and alerting on expiry.

**Your secrets.** If a teammate's laptop with the `.env` file gets lost, you've lost the secrets. The remediation is a secrets vault (AWS Secrets Manager, HashiCorp Vault) that doesn't depend on any single person's laptop.

For a class project, you accept all of these as known limitations. Naming them is the lesson. Real production systems methodically eliminate or replicate each SPOF, prioritizing by likelihood × impact.

### §20. Portability and porting

Your current setup runs on `docker-compose up`. The same setup, with minor changes, runs almost anywhere docker runs.

**The portable parts (no change needed):**

- The Dockerfile. The image you build runs the same anywhere.  
- The Python code. WSGI behind gunicorn behind nginx is a standard pattern.  
- The Postgres data layer. Postgres runs identically everywhere.  
- The nginx config. Almost unchanged across platforms.

**What changes when you port:**

- **The host.** `docker-compose up` works on Linux, macOS, and Windows. The host-specific friction is in volume permissions (file ownership differs between docker-on-mac and docker-on-linux) and networking (docker-compose's network behavior varies between Docker Desktop and native Linux Docker).  
- **The deploy target.** The release workflow's "deploy" step SSHes to a specific host with a specific path. Swap EC2 for DigitalOcean: change the SSH host, the SSH key, possibly the deploy path. The rest of the workflow is the same.  
- **TLS certs.** Self-signed for development works everywhere. Real Let's Encrypt certs require a publicly-resolvable domain pointed at the host — different platforms have different DNS workflows.  
- **Networking.** On your laptop, `https://localhost` is the entry point. On a public host, it's your domain. The compose file may need adjustment (e.g., exposing nginx on the right interface), but the structure stays the same.

**Running the stack locally on a teammate's laptop:**

git clone \<your team repo\>

cd \<repo\>

docker-compose up \--build

That should be it, assuming:

- They have Docker installed.  
- The `.env` file is recreated locally (it's gitignored — they need their own).  
- The self-signed cert is regenerated (also gitignored — the `openssl` one-liner from §7).  
- Their host has port 443 free.

If your README's "Running the production stack" section captures these three things, a new teammate can run your stack in 5 minutes. That's the portability win.

**The contract that makes this work:** *build a container, push to a registry, deploy to a target.* Every part of that contract is implementation-agnostic. The container is portable. The registry is interchangeable. The target is replaceable. As long as the contract holds, your project isn't tied to any specific cloud or deploy mechanism.

---

## Part VI — Per-Role LLM Probe Prompts (Full Versions)

These are the canonical fuller prompts referenced from each role's LLM-probe sub-question in the assignment. The inline versions in the assignment are short summaries; these expand them with how-to-use guidance, what to look for in the response, and what to write up.

### §21. Frontend probe prompt (full)

**How to use it.** Open a fresh conversation with your LLM. Paste your nginx security header config (the `add_header` directives) and your CSP value. Send the prompt. Push back when the response is vague — "what specifically would break in our app if we did that?" or "give me a concrete example of an attack that gets through."

**The prompt:**

I'm the frontend person on a team hardening a Flask web application.

We just added nginx in front of our app and I'm responsible for

browser-side hardening.

Here's our nginx security header config:

\[paste your add\_header directives and related config\]

Here's our Content-Security-Policy:

\[paste your CSP, or "we don't have one yet"\]

Here's a 1-2 sentence description of what our app does and what

loads in the browser:

\[your project description — framework, external scripts, fonts,

inline JS, etc.\]

Evaluate this against current frontend security best practices.

Identify:

(a) Headers missing for our use case and what they protect against.

(b) Values too strict for our app — what would visibly break if

    we shipped them.

(c) What an attacker could still do against our app despite these

    headers — what these headers don't cover.

For each, tell me what you'd change and why.

**What to look for in the response.** Headers you didn't know about (HSTS preload, Permissions-Policy, COEP/COOP). Values that look fine in isolation but conflict with what your app does (a strict CSP that blocks framework-injected inline JS). Things the LLM hedges on — "this depends on whether your app uses iframes…" is the LLM telling you it needs more context; give it more. Attacks the headers don't cover — CSP doesn't stop CSRF, HSTS doesn't stop XSS. Recognizing what the headers DON'T cover is part of the lesson.

**What to write up.** A short reflection covering: what the LLM identified that surprised you (one or two things), what you'd push back on or fact-check before applying, what you'd actually change in your nginx.conf, and what's still on your "to harden later" list.

### §22. Backend probe prompt (full)

**How to use it.** Open a fresh conversation. Paste your gunicorn.conf.py and the relevant parts of your Flask production config (debug flag, secret key handling, ProxyFix setup, error handlers). Ask follow-ups when vague — "is that setting actually a problem if we're behind nginx?" or "what would I see in the logs if that broke?"

**The prompt:**

I'm the backend person on a team hardening a Flask web application.

We're putting gunicorn in front of our Flask app and moving off

flask run for the first time. I own the Python process layer.

Here's our gunicorn.conf.py:

\[paste your gunicorn config\]

Here's our Flask production config — debug flag, secret key handling,

ProxyFix setup, error handlers:

\[paste from your app factory, config object, error handlers\]

Here's our app's traffic pattern in 1-2 sentences:

\[rough request rate, CPU vs I/O bound, any slow external calls\]

Audit this for production readiness. Identify:

(a) Settings that are wrong or absent for production — debug mode,

    secret from source, missing timeouts, wrong worker count.

(b) Information-leakage paths — tracebacks, error messages, default

    endpoints that leak framework details.

(c) Anything that would behave correctly under flask run but break

    (or behave differently) under gunicorn, or vice versa.

For each, tell me what you'd change and why.

**What to look for in the response.** Settings you copied from a canonical config without thinking about whether they fit your project — worker count is the classic one. Things `flask run` does that gunicorn doesn't (auto-reload, debug pin, the interactive debugger). The ProxyFix gotcha — if you don't have it configured, the LLM should flag it; if you do, it might still flag it as misconfigured. Error handlers that return tracebacks — the Flask default in production is fine; if your team wrote custom error handlers, they may have re-introduced the leak.

**What to write up.** A short reflection: what the LLM identified that you'd actually fix, anything that doesn't apply to your project and why, what you learned about the gunicorn-Flask boundary that you didn't know, what's still on your "to harden later" list.

### §23. DB/security probe prompt — 4-person team variant (full)

**Use this prompt if you're on a 4-person team and your coordination teammate handles the deploy pipeline.** If you're on a 3-person team (the standard), use §24 instead.

**How to use it.** Open a fresh conversation. Paste your nginx server block and your `attack_paths.json`. Push back on hand-wavy responses — "give me a concrete request that would hit that" or "show me what the attack looks like as a curl command."

**The prompt:**

I'm the security person on a team hardening a Flask web application.

We've added nginx in front and we have a parametrized pytest test

that hits a list of known-bad paths and asserts nginx returns

404/403 for all of them.

Here's our nginx server block:

\[paste your full server block — all location blocks, headers, rate

limits\]

Here's our attack\_paths.json list:

\[paste the contents\]

Here's a short description of our app — what inputs it accepts,

what routes it exposes, what authentication it uses:

\[1-2 sentences about your project\]

Describe attacks against this app that our path-list test would

NOT catch. For each attack:

(a) Describe the attack concretely — what does the malicious

    request look like?

(b) Walk through whether our nginx config would block it. If yes,

    explain which directive does the blocking. If no, explain

    what Flask would see.

(c) If our config wouldn't block it, what would we need to add to

    nginx, Flask, or somewhere else?

Focus on attacks where the bad behavior isn't a fixed URL path —

injection, slowloris, OAuth callback abuse, content-type confusion,

oversized requests, etc.

**What to look for in the response.** Whole categories of attack that don't show up in a URL-path list — SQL/command/template injection, slowloris, oversized payloads, host-header attacks. Attacks caught not by nginx but by Flask or the framework — useful for understanding what nginx does and doesn't do. Attacks that need configuration you haven't added — request size limits, slow-client timeouts, header validation. The LLM's confidence level — if it's very confident, fact-check it; nginx's behavior on edge cases is genuinely subtle.

**What to write up.** A short reflection: one or two categories of attack the path-list approach misses (named and explained in your own words). Whether your nginx config catches them, and if not what you'd add. What this exercise taught you about the gap between "test passing" and "actually hardened." What's still on your "to harden later" list.

### §24. DB/security combined probe — 3-person team standard (full)

**Use this prompt if you're on a 3-person team (the standard).** Your security surface includes the deploy pipeline, so this is the combined version. If you're on a 4-person team, use §23 instead.

**How to use it.** Open a fresh conversation. Paste your nginx config, attack\_paths.json, release workflow, and secrets handling. Walk through the full surface in one conversation — don't stop after the nginx section. The LLM will give a long initial response covering all four areas; follow up with concrete drill-downs on each ("show me the curl command for that attack", "what would I see in the Actions log if that leak happened").

**The prompt:**

I'm the security person on a small team (three people) hardening a

Flask web application. On our team I own the full security surface

— the network edge, the attack-path tests, AND the deploy pipeline.

I'm running this as one combined security probe rather than as two

separate ones.

Here's our nginx server block:

\[paste your full server block\]

Here's our attack\_paths.json list:

\[paste the contents\]

Here's our GitHub Actions release workflow:

\[paste your full workflow YAML\]

Here's how we handle secrets — GitHub Actions secrets, docker-compose

references, anything else that touches credentials:

\[paste relevant sections plus 2-3 sentences describing your setup\]

Here's a short description of our app:

\[1-2 sentences about your project\]

Walk the full security surface for me. Cover, in order:

(a) Attacks against this app that our path-list test would NOT catch.

    For each, describe the attack concretely, and explain whether

    our nginx config blocks it.

(b) Secrets-leakage paths in our deploy — places where a secret

    could end up visible to someone who shouldn't see it (job logs,

    error messages, git history, fork PRs, artifacts).

(c) What a hostile collaborator with commit access could do. What

    damage could they cause before someone notices?

(d) What's missing from a production-grade deploy that we'd want

    to add — health checks, rollback, deployment notifications,

    blue/green, etc.

For each, tell me what you'd change and why.

**What to look for in the response.** The LLM will often give a long response covering all four areas. That's fine for a first pass — the value is in the follow-ups. Push back on specifics: for attacks (a) get concrete request examples (vague descriptions don't help you write nginx config); for leakage paths (b) get specific log lines (force the LLM to construct worst-case output); for hostile collaborator (c) force specifics ("give me a specific malicious commit \+ tag"); for missing pieces (d) rank them ("of the things you listed, which two would I add first if I had a free afternoon?").

**What to write up.** A short reflection: the two or three most concrete things the LLM identified across all four areas. What you'd actually change in nginx, workflow, or secrets handling. What's still on your "to harden later" list. Anything you'd push back on or fact-check.

**Why one probe rather than two.** On a 4-person team, security and coordination are two roles and they run two probes. On a 3-person team, you ARE the team's security and coordination — so the probe walks the surface continuously, the way you'd actually think about it as one job. The LLM gives better recommendations when it sees the whole picture: a secret leaking from the deploy pipeline can compromise the nginx config; an nginx misconfiguration can expose what a hostile collaborator could exploit. One conversation surfaces those connections.

### §25. Coordination probe prompt — 4-person teams only (full)

**Use this prompt only if your team has 4 people and you're the dedicated coordination role.** On a 3-person team, the coordination work is covered by the DB/security person via §24.

**How to use it.** Open a fresh conversation. Paste your release workflow and the relevant docker-compose sections. Push back when the LLM speculates — "where in the log would that show up?" or "what would the bad actor do specifically with that?"

**The prompt:**

I'm the coordination person on a team hardening a Flask web

application's deploy pipeline. We're moving from "deploy by SSHing

to a server" to a GitHub Actions workflow that runs on tag pushes.

Here's our .github/workflows/release.yml:

\[paste your full workflow YAML\]

Here's the relevant part of our docker-compose.yml — environment

variables, secrets references, anything that touches credentials:

\[paste relevant sections\]

Here's how we're handling secrets today:

\[2-3 sentences — which secrets exist, where they live, who has

access\]

Audit this for:

(a) Secrets-leakage paths — places where a secret could end up

    visible to someone who shouldn't see it (job logs, error

    messages, git history, fork PRs, artifacts).

(b) What a hostile collaborator with commit access could do —

    what damage could they cause before someone notices?

(c) What's missing from a production-grade deploy that we'd want

    to add — health checks, rollback, deployment notifications,

    blue/green, anything else.

For each, tell me what you'd change and why.

**What to look for in the response.** Secrets that get echoed inadvertently — `echo $TOKEN` in a debug step, error messages including env var values, build steps that copy `.env` into image layers. The fork-PR problem — by default, Actions doesn't pass secrets to workflows triggered by PRs from forks, but workflows that DO expose secrets to PRs are a real attack surface. The "hostile collaborator with commit access" framing is uncomfortable but useful — if a teammate's account got compromised, what's the worst they could do via a malicious commit \+ tag? Production-grade features missing from your pipeline — health checks, rollback, blue/green deploys. The worked example deploys naively; the LLM should flag the absences.

**What to write up.** A short reflection: one or two leakage paths the LLM flagged that you'd actually close. What a hostile collaborator could do, named concretely. The gap between your current deploy and "production-grade." What you'd push back on or fact-check.

---

## Part VII — Forward Pointers

These topics came up in lecture but aren't required by the assignment. Read these sections when you encounter the related problem in your project.

### §A. alembic and schema migrations

Your project's schema lives in your model classes (`User`, `Post`, etc.). When you change a model — add a column, rename a field, drop a table — the database needs to match the new model definition. alembic is the canonical Python tool for managing that change as versioned migrations.

**When you'd reach for it.** Someone on your team adds a column to a model. The app works locally because they ran a migration locally. The change gets pushed. Other teammates pull the code, but their local database still has the old schema — the app crashes or behaves wrong. In production, the schema is the production schema; deploying new code without migrating breaks prod the same way. alembic prevents this by making every schema change a versioned, code-reviewed migration file that all environments apply in order.

**The five commands you need:**

alembic init alembic                                \# one-time setup

alembic revision \--autogenerate \-m "add user.role" \# generate migration from model diff

alembic upgrade head                                \# apply all pending migrations

alembic current                                     \# what version is this DB on

alembic history                                     \# list all migrations in order

**The gotcha:** `--autogenerate` is a *draft*, not a final. It diffs your models against the current DB schema and generates code to bring them in sync, but it has known blind spots. Column renames look like DROP \+ ADD (it loses data). Server-side defaults are often missed. Read every line of every generated migration before committing it.

**Where to put migrations in your deploy.** Run `alembic upgrade head` *before* starting the new app version. If migrations fail, the old app keeps running with the old schema. If migrations succeed, the new app starts with the new schema. Never run migrations on app startup — concurrent app instances would race.

For Week 8, alembic is forward-pointer material. If your team is making schema changes weekly, adopt it. If your schema is stable, you don't need it yet.

### §B. Let's Encrypt and real certs

Self-signed certs are fine for this week. Real certs are Week 9 work, but if you want to host your project publicly before then, here's the path.

**Let's Encrypt** is a free certificate authority. They issue real TLS certs (trusted by every browser) via an automated protocol called ACME. The certs are valid for 90 days, with automated renewal expected.

**The three-step dance:**

1. **Ask.** Your machine (running a tool called `certbot`) asks Let's Encrypt for a cert for `yourapp.com`.  
2. **Prove.** Let's Encrypt: "prove you control yourapp.com — serve this token at `https://yourapp.com/.well-known/acme-challenge/<token>`."  
3. **Issue.** certbot serves the token from your web server, Let's Encrypt verifies, cert is issued and downloaded.

The renewal is automated — certbot runs every day via a systemd timer or cron job, checks if any cert is within 30 days of expiry, and re-runs the dance.

**Requirements you don't have on a self-signed setup:**

- A publicly-resolvable domain name. `yourapp.com` must have a DNS A record pointing at your host's public IP.  
- Port 80 open to the world. The ACME challenge happens over HTTP on port 80\.  
- A way to run certbot. Easiest: a certbot container in your docker-compose, or certbot running on the host with the right nginx integration.

**The diff with self-signed.** Two lines of nginx.conf change. Your cert paths point to the certbot-managed files (`/etc/letsencrypt/live/yourapp.com/fullchain.pem` and `privkey.pem`) instead of your self-signed pair. Everything else in nginx.conf stays the same.

Forward pointer: this is Week 9 work. If you're hosting publicly before then, the certbot docs ([https://certbot.eff.org/](https://certbot.eff.org/)) walk you through setup for any platform.

### §C. Agent docs (CLAUDE.md / AGENTS.md)

A `CLAUDE.md` file at your repo root is a document written for a coding agent (Claude Code, Cursor, etc.) that gives the agent the context it needs to be productive in your codebase. The same document also works for new human teammates — anyone joining your project needs the same orientation.

**What goes in it:**

- **Architecture in one paragraph.** What's in this repo, what each major piece does.  
- **Local development.** How to start the stack. One command if possible.  
- **Production stack.** What each container does, how they connect, what ports.  
- **Common tasks.** Add a migration, add a route, add a test, debug CI. Concrete recipes.  
- **Conventions.** Naming, file organization, where new code goes.  
- **Gotchas.** Anything that has bitten the team — things a new person would otherwise have to learn the hard way.

Length: 200-500 lines. Keep it shorter than you think. The "common tasks" section is the highest-value: it turns "I want to add a feature" into a deterministic sequence of steps.

**Why AGENTS.md exists too.** Different agents look for different filenames. Cursor reads `.cursorrules`. Claude Code reads `CLAUDE.md`. Some look for a generic `AGENTS.md`. Pragmatic answer: write the content once in `CLAUDE.md`, symlink `AGENTS.md` to it (`ln -s CLAUDE.md AGENTS.md`). On Windows where symlinks are awkward, copy the content via a pre-commit hook.

For Week 8 this is forward-pointer material. If your team is using a coding agent productively in your project, add a CLAUDE.md — it's a 30-minute task that pays for itself many times over. If you're not using agents heavily yet, this can wait.

---

## Wrap-up

The production stack you built this week is the foundation for everything Week 9 covers — real domains, real certs, real hosting, the actual project check-in where your team's app runs on the stack you just hardened.

Read sections as you need them. The assignment points you to specific sections by number; use those as the entry points. The depth here is meant to be reference material you return to when your project actually hits the problem the section addresses.  
