"""Production WSGI config — Trail-checker (Week 8).

Ryan (ryan-hardening): tune workers, worker_class, timeouts for OpenWeather I/O.
"""

bind = "0.0.0.0:8000"
workers = 3
worker_class = "sync"
timeout = 30
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
max_requests = 1000
max_requests_jitter = 50
preload_app = True
