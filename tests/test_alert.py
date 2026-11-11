"""Tests for leadrelay.alert against a fake Slack running on this Mac (no internet)."""

import json

import pytest

from fake_http import FakeHttpServer
from leadrelay.alert import AlertError, format_message, send_alert

RECORD = {
    "lead_id": "lead_1",
    "display_name": "Lowell Bast",
    "date_created": "2025-05-20T12:14:56.409000+00:00",
    "status_label": "Potential",
    "lead_email": "lowell@example.com",
    "lead_owner": "Lucija Bitunjac",
    "funnel": "DE ACADEMY Direct VSL",
    "owner_found": True,
}


# ---------- the message text ----------

def test_message_has_all_seven_fields_in_order():
    assert format_message(RECORD) == (
        ":rotating_light: *New Lead Alert*\n"
        "*Name:* Lowell Bast\n"
        "*Lead ID:* lead_1\n"
        "*Created Date:* 2025-05-20T12:14:56.409000+00:00\n"
        "*Label:* Potential\n"
        "*Email:* lowell@example.com\n"
        "*Lead Owner:* Lucija Bitunjac\n"
        "*Funnel:* DE ACADEMY Direct VSL"
    )


def test_missing_owner_shows_unassigned_and_na():
    record = {**RECORD, "owner_found": False, "lead_owner": None, "lead_email": None, "funnel": None}
    text = format_message(record)
    assert "*Lead Owner:* UNASSIGNED" in text
    assert "*Email:* N/A" in text and "*Funnel:* N/A" in text


def test_special_characters_cannot_ping_the_channel():
    text = format_message({**RECORD, "display_name": "<!channel> Tom & Jerry"})
    assert "*Name:* &lt;!channel&gt; Tom &amp; Jerry" in text


# ---------- sending ----------

@pytest.fixture
def slack():
    fake = FakeHttpServer()
    yield fake
    fake.close()


@pytest.fixture
def waits():
    return []


def send(slack, waits, record=RECORD):
    send_alert(slack.url + "/services/T000/B000/secret", record, timeout=2, sleep=waits.append)


def test_success_posts_json_text(slack, waits):
    slack.replies = [(200, b"ok")]
    send(slack, waits)
    request = slack.requests[0]
    assert request["method"] == "POST"
    assert request["headers"]["Content-Type"] == "application/json"
    assert json.loads(request["body"]) == {"text": format_message(RECORD)}
    assert waits == []


def test_server_error_is_retried_then_succeeds(slack, waits):
    slack.replies = [(500, b""), (200, b"ok")]
    send(slack, waits)
    assert len(slack.requests) == 2 and waits == [1]


def test_rate_limit_waits_as_slack_asks(slack, waits):
    slack.replies = [(429, b"", {"Retry-After": "3"}), (200, b"ok")]
    send(slack, waits)
    assert waits == [3]


def test_rate_limit_wait_is_capped(slack, waits):
    slack.replies = [(429, b"", {"Retry-After": "120"}), (200, b"ok")]
    send(slack, waits)
    assert waits == [5]


def test_failing_every_time_raises_after_3_attempts(slack, waits):
    slack.replies = [(503, b"")] * 3
    with pytest.raises(AlertError, match="after 3 attempts"):
        send(slack, waits)
    assert len(slack.requests) == 3


def test_bad_url_raises_at_once_without_leaking_the_secret(slack, waits):
    slack.replies = [(404, b"no_service")]
    with pytest.raises(AlertError) as error:
        send(slack, waits)
    assert "HTTP 404" in str(error.value)
    assert "secret" not in str(error.value) and "127.0.0.1" not in str(error.value)
    assert len(slack.requests) == 1 and waits == []


def test_no_slack_at_all_is_retried_then_raises(waits):
    with pytest.raises(AlertError, match="network error"):
        send_alert("http://127.0.0.1:9/hook", RECORD, timeout=1, sleep=waits.append)
    assert waits == [1, 2]
