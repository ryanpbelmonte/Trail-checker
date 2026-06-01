"""Production WSGI config — Trail-checker (Week 8)."""

# TCP bind for docker-compose; nginx proxies to app:8000 on the internal network.
bind = "0.0.0.0:8000"

# Rule of thumb: (2 * CPU cores) + 1. Tune after measuring real load.
workers = 3

# sync is appropriate for this app; switch to gthread if workers spend
# most of their time waiting on external APIs (OpenWeather, etc.).
worker_class = "sync"

timeout = 30
graceful_timeout = 30

accesslog = "-"
errorlog = "-"
loglevel = "info"

max_requests = 1000
max_requests_jitter = 50
preload_app = True
