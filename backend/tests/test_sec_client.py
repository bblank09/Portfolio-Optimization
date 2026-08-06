import time

import httpx
import pytest
import tenacity

from backend.app.sec.client import SecOpenDataClient


def test_sec_client_builds_configured_headers():
    client = SecOpenDataClient(api_key="abc123", base_url="https://api.sec.or.th")
    headers = client._headers()
    assert headers["Ocp-Apim-Subscription-Key"] == "abc123"
    assert headers["Accept"] == "application/json"


def test_sec_client_treats_204_as_empty_payload(monkeypatch):
    def fake_get(*args, **kwargs):
        request = httpx.Request("GET", "https://api.sec.or.th/empty")
        return httpx.Response(204, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    client = SecOpenDataClient(api_key="abc123", base_url="https://api.sec.or.th")
    assert client.get("/empty") == {}


def test_sec_client_retries_a_transient_server_error_then_succeeds(monkeypatch):
    # SEC's API is flaky under load; a single 503 mid-download must not kill
    # a multi-thousand-request full-universe pull -- it should retry and
    # succeed rather than raising immediately.
    monkeypatch.setattr(tenacity.nap.time, "sleep", lambda seconds: None)
    request = httpx.Request("GET", "https://api.sec.or.th/flaky")
    responses = [
        httpx.Response(503, request=request),
        httpx.Response(503, request=request),
        httpx.Response(200, request=request, json={"ok": True}),
    ]
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        response = responses[calls["count"]]
        calls["count"] += 1
        return response

    monkeypatch.setattr(httpx, "get", fake_get)
    client = SecOpenDataClient(api_key="abc123", base_url="https://api.sec.or.th")

    result = client.get("/flaky")

    assert result == {"ok": True}
    assert calls["count"] == 3


def test_sec_client_gives_up_after_three_attempts_on_persistent_server_error(monkeypatch):
    monkeypatch.setattr(tenacity.nap.time, "sleep", lambda seconds: None)
    request = httpx.Request("GET", "https://api.sec.or.th/down")
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return httpx.Response(503, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    client = SecOpenDataClient(api_key="abc123", base_url="https://api.sec.or.th")

    with pytest.raises(httpx.HTTPStatusError):
        client.get("/down")

    assert calls["count"] == 3


def test_sec_client_does_not_retry_a_client_error(monkeypatch):
    # A 404/401/etc. will never succeed on retry -- retrying it just delays
    # the (correct) failure and wastes SEC's rate-limit budget.
    monkeypatch.setattr(tenacity.nap.time, "sleep", lambda seconds: None)
    request = httpx.Request("GET", "https://api.sec.or.th/missing")
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return httpx.Response(404, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    client = SecOpenDataClient(api_key="abc123", base_url="https://api.sec.or.th")

    with pytest.raises(httpx.HTTPStatusError):
        client.get("/missing")

    assert calls["count"] == 1
