"""Pytest discovery anchor.

Ensures the repo root is on `sys.path` and sets the environment flags that
must be in place BEFORE `app.py` is imported by any test module.

Notes:
- `TESTING=1` disables CSRF and the login rate limiter so the test client
  can POST without acquiring tokens.
- `DATABASE_URL` uses an in-memory SQLite database so tests do not require
  Postgres in CI.
- `SECRET_KEY` is set so app.py does not fall back to the dev default.
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires docker production stack on https://localhost",
    )
