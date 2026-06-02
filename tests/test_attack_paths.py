"""§10 — nginx blocks known scanner paths before Flask.

Requires production stack: docker compose up -d, then:

    pytest tests/test_attack_paths.py -v -m integration
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parents[1]
with open(ROOT / "attack_paths.json", encoding="utf-8") as f:
    PATHS = json.load(f)

BASE = "https://localhost"


@pytest.mark.integration
@pytest.mark.parametrize("path", PATHS)
def test_nginx_blocks(path: str) -> None:
    r = requests.get(BASE + path, verify=False, timeout=5)
    assert r.status_code in (404, 403), (
        f"{path} returned {r.status_code} — nginx let it through"
    )
