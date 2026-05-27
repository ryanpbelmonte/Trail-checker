"""Pytest plumbing for end-to-end (Playwright) tests.

Sets TESTING and a file-backed SQLite DATABASE_URL BEFORE app.py is
imported. The file path is intentionally a per-pytest-session tempfile
so:

- The running app server and the test process can share the same DB
  (in-memory SQLite is per-connection and would not work here).
- Two test runs (xdist workers, two devs on a shared box, CI matrix
  workers) cannot collide on the same /tmp filename.
- The file lives outside the repo and is cleaned up at session end,
  so nothing leaks back into git.

Compare with tests/conftest.py which uses in-memory SQLite — that is
correct for unit/integration tests that go through Flask's test client
in-process, but it cannot be reached by a separately-launched server
process.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from werkzeug.serving import make_server


_E2E_DB_PATH = (
    Path(tempfile.gettempdir()) / f"trail_checker_e2e_{uuid.uuid4().hex}.db"
)

# Override tests/conftest.py in-memory SQLite — Playwright hits a real server
# process that opens its own connections; file-backed DB is shared across them.
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{_E2E_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-e2e"

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
)


@dataclass(frozen=True)
class LiveServer:
    """Base URL for the threaded Werkzeug server used by Playwright tests."""

    url: str


def pytest_sessionstart(session):
    """Start every e2e session from a clean DB on disk."""
    if _E2E_DB_PATH.exists():
        _E2E_DB_PATH.unlink()
    _E2E_DB_PATH.touch(mode=0o600, exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
    """Remove the tempfile DB so /tmp does not accumulate test artifacts."""
    try:
        if _E2E_DB_PATH.exists():
            _E2E_DB_PATH.unlink()
    except OSError:
        pass


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {"headless": True}


@pytest.fixture(scope="session")
def live_server():
    """Run the real Flask app in a background thread for browser-driven tests."""
    from app import app, engine
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(engine)
    app.config["TESTING"] = True

    httpd = make_server("127.0.0.1", 0, app)
    port = httpd.server_port
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{port}"
    yield LiveServer(url=base_url)

    httpd.shutdown()
    thread.join(timeout=5)
