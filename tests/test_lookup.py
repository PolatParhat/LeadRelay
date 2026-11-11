"""Tests for leadrelay.lookup against a small fake web server on this Mac (no internet)."""

import json

import pytest

from fake_http import FakeHttpServer
from leadrelay.lookup import OwnerLookupError, fetch_owner

OWNER_FILE = {
    "lead_id": "lead_1",
    "display_name": "Lowell Bast",
    "lead_email": "lowell@example.com",
    "lead_owner": "Lucija Bitunjac",
    "funnel": "DE ACADEMY Direct VSL",
    "status_label": "Potential",
    "date_created": "2025-05-20T12:14:56.409000+00:00",
}


@pytest.fixture
def bucket():
    fake = FakeHttpServer()
    yield fake
    fake.close()


@pytest.fixture
def waits():
    """Records the backoff waits instead of really sleeping, so tests stay fast."""
    return []


def lookup(bucket, waits, lead_id="lead_1"):
    return fetch_owner(lead_id, base_url=bucket.url, timeout=2, sleep=waits.append)


def test_found_returns_the_three_owner_fields(bucket, waits):
    bucket.replies = [(200, json.dumps(OWNER_FILE).encode())]
    assert lookup(bucket, waits) == {
        "lead_email": "lowell@example.com",
        "lead_owner": "Lucija Bitunjac",
        "funnel": "DE ACADEMY Direct VSL",
    }
    assert [r["path"] for r in bucket.requests] == ["/lead_1.json"]


@pytest.mark.parametrize("status", [403, 404])
def test_missing_file_returns_none_without_retrying(bucket, waits, status):
    bucket.replies = [(status, b"")]
    assert lookup(bucket, waits) is None
    assert len(bucket.requests) == 1 and waits == []


def test_server_error_is_retried_then_succeeds(bucket, waits):
    bucket.replies = [(500, b""), (503, b""), (200, json.dumps(OWNER_FILE).encode())]
    assert lookup(bucket, waits)["lead_owner"] == "Lucija Bitunjac"
    assert waits == [1, 2]  # exponential backoff


def test_server_error_every_time_raises_after_3_attempts(bucket, waits):
    bucket.replies = [(500, b"")] * 3
    with pytest.raises(OwnerLookupError, match="after 3 attempts"):
        lookup(bucket, waits)
    assert len(bucket.requests) == 3


def test_other_client_error_raises_without_retrying(bucket, waits):
    bucket.replies = [(400, b"")]
    with pytest.raises(OwnerLookupError, match="HTTP 400"):
        lookup(bucket, waits)
    assert waits == []


def test_no_server_at_all_is_retried_then_raises(waits):
    nobody_listening = "http://127.0.0.1:9"  # port 9: nothing runs there
    with pytest.raises(OwnerLookupError, match="network error"):
        fetch_owner("lead_1", base_url=nobody_listening, timeout=1, sleep=waits.append)
    assert waits == [1, 2]


def test_file_for_another_lead_raises(bucket, waits):
    bucket.replies = [(200, json.dumps({**OWNER_FILE, "lead_id": "lead_2"}).encode())]
    with pytest.raises(OwnerLookupError, match="belongs to lead_2"):
        lookup(bucket, waits)


def test_not_json_raises(bucket, waits):
    bucket.replies = [(200, b"<html>oops</html>")]
    with pytest.raises(OwnerLookupError, match="not valid JSON"):
        lookup(bucket, waits)


def test_missing_owner_field_becomes_none(bucket, waits):
    partial = {"lead_id": "lead_1", "lead_email": "lowell@example.com"}
    bucket.replies = [(200, json.dumps(partial).encode())]
    assert lookup(bucket, waits) == {
        "lead_email": "lowell@example.com", "lead_owner": None, "funnel": None,
    }
