from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.api import data_status as data_status_module
from backend.app.main import app


def test_data_status_returns_the_manifest_nav_as_of_date():
    # A deployer's users have no way to know if "today's" backtest is using
    # NAV data from yesterday or from six months ago unless the app tells
    # them -- this must reflect the real manifest, not a hardcoded value.
    client = TestClient(app)

    response = client.get("/api/data-status")

    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "sec_open_data"
    assert body["nav_as_of"]  # non-empty
    # Must match the real committed manifest, not be fabricated.
    import json

    manifest = json.loads(Path("data/sec/normalized/sec_data_manifest.json").read_text())
    assert body["nav_as_of"] == manifest["end"]
    assert body["fund_count"] == manifest["fund_count"]


def test_data_status_returns_the_manifest_nav_start_date():
    # The frontend uses this to bound the date-range picker so a user can't
    # pick a start date before any NAV data exists -- must reflect the real
    # manifest, not a hardcoded value.
    client = TestClient(app)

    response = client.get("/api/data-status")

    assert response.status_code == 200
    body = response.json()
    import json

    manifest = json.loads(Path("data/sec/normalized/sec_data_manifest.json").read_text())
    assert body["nav_start"] == manifest["start"]


def test_data_status_returns_503_when_manifest_is_missing():
    client = TestClient(app)
    with patch.object(data_status_module, "MANIFEST_PATH", Path("data/sec/normalized/does_not_exist.json")):
        response = client.get("/api/data-status")

    assert response.status_code == 503
    assert response.json()["code"] == "NAV_CACHE_MISSING"
