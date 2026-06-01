# gunicorn.conf.py — production WSGI server config for Trail-checker

# TCP bind for docker-compose; nginx will proxy to app:8000 on the internal network.
# Unix socket alternative: bind = "unix:/tmp/gunicorn.sock"
bind = "0.0.0.0:8000"

# Rule of thumb: (2 * CPU cores) + 1. Tune after measuring real load.
workers = 3

# sync is appropriate for this app; switch to gthread if workers spend
# most of their time waiting on external APIs (OpenWeather, etc.).
worker_class = "sync"

# Kill hung workers; allow in-flight requests to finish on restart.
timeout = 30
graceful_timeout = 30

# Log to stdout/stderr so Docker captures output.
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Restart workers periodically to mitigate slow memory growth.
max_requests = 1000
max_requests_jitter = 50

# Load the Flask app before forking workers for faster startup.
preload_app = True
