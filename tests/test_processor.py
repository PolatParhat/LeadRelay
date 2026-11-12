"""Tests for the processor Lambda.

Fakes: S3 and SSM (moto), the owner bucket and Slack (local FakeHttpServer).
Nothing leaves this Mac.
"""

import json
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from moto import mock_aws

from conftest import BUCKET
from fake_http import FakeHttpServer
from leadrelay import processor, storage
from leadrelay.config import SecretStore, load_settings

LEAD_ID = "lead_1"
NOW = datetime(2026, 11, 11, 12, 40, tzinfo=timezone.utc)
CRM_EVENT = {
    "subscription_id": "whsub_1",
    "event": {
        "object_type": "lead", "action": "created", "lead_id": LEAD_ID,
        "data": {"display_name": "Lowell Bast", "status_label": "Potential",
                 "date_created": "2025-05-20T12:14:56.409000+00:00"},
    },
}
OWNER_FILE = {"lead_id": LEAD_ID, "lead_email": "lowell@example.com",
              "lead_owner": "Lucija Bitunjac", "funnel": "DE ACADEMY Direct VSL"}
FOUND = (200, json.dumps(OWNER_FILE).encode())
MISSING = (403, b"")
SLACK_OK = (200, b"ok")


def sqs_event(key=storage.source_key(LEAD_ID), receive_count=1, body=None):
    """What SQS hands the Lambda: one message whose body is the S3 notification."""
    if body is None:
        body = {"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Put",
                             "s3": {"bucket": {"name": BUCKET}, "object": {"key": key}}}]}
    return {"Records": [{
        "messageId": "msg-1",
        "body": json.dumps(body),
        "attributes": {"ApproximateReceiveCount": str(receive_count)},
        "eventSource": "aws:sqs",
    }]}


class World:
    """Everything one test needs, wired together."""

    def __init__(self):
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=BUCKET)
        self.owner_bucket = FakeHttpServer()
        self.slack = FakeHttpServer()
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/leadrelay/slack_webhook_url",
                          Value=self.slack.url + "/services/T0/B0/x", Type="SecureString")
        self.secrets = SecretStore(ssm)
        self.settings = load_settings({"BUCKET_NAME": BUCKET, "OWNER_BASE_URL": self.owner_bucket.url})
        storage.put_json(self.s3, BUCKET, storage.source_key(LEAD_ID), CRM_EVENT)

    def run(self, event=None, now=NOW, **kwargs):
        return processor.handle(event or sqs_event(**kwargs), self.settings, self.s3, self.secrets, now=now)

    def alerts(self):
        return [json.loads(r["body"])["text"] for r in self.slack.requests]

    def enriched(self):
        return storage.get_json(self.s3, BUCKET, storage.target_key(LEAD_ID))

    def marker(self):
        return storage.read_marker(self.s3, BUCKET, LEAD_ID)

    def close(self):
        self.owner_bucket.close()
        self.slack.close()


@pytest.fixture
def world():
    with mock_aws():
        w = World()
        yield w
        w.close()


NO_FAILURES = {"batchItemFailures": []}
FAILED = {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}


# ---------- normal flow ----------

def test_owner_found_enriches_and_alerts_once(world):
    world.owner_bucket.replies = [FOUND]
    world.slack.replies = [SLACK_OK]
    assert world.run() == NO_FAILURES
    assert world.enriched()["lead_owner"] == "Lucija Bitunjac"
    assert world.enriched()["owner_found"] is True
    assert len(world.alerts()) == 1 and "*Lead Owner:* Lucija Bitunjac" in world.alerts()[0]
    assert world.marker().status == "sent"


def test_duplicate_message_does_not_alert_twice(world):
    world.owner_bucket.replies = [FOUND, FOUND]
    world.slack.replies = [SLACK_OK, SLACK_OK]
    world.run()
    assert world.run() == NO_FAILURES
    assert len(world.alerts()) == 1


def test_s3_test_event_is_ignored(world):
    assert world.run(sqs_event(body={"Service": "Amazon S3", "Event": "s3:TestEvent"})) == NO_FAILURES
    assert world.owner_bucket.requests == [] and world.alerts() == []


def test_url_encoded_key_is_decoded(world):
    world.owner_bucket.replies = [FOUND]
    world.slack.replies = [SLACK_OK]
    # S3 URL-encodes the key inside event notifications ("/" can arrive as "%2F")
    assert world.run(key="source%2Fcrm_event_lead_1.json") == NO_FAILURES


# ---------- missing-owner policy ----------

@pytest.mark.parametrize("try_number", [1, 5])
def test_missing_owner_before_last_try_retries_without_alert(world, try_number):
    world.owner_bucket.replies = [MISSING]
    assert world.run(receive_count=try_number) == FAILED
    assert world.alerts() == []
    assert world.marker() is None
    with pytest.raises(world.s3.exceptions.NoSuchKey):
        world.enriched()


def test_missing_owner_on_last_try_alerts_unassigned(world):
    world.owner_bucket.replies = [MISSING]
    world.slack.replies = [SLACK_OK]
    assert world.run(receive_count=6) == NO_FAILURES
    assert world.enriched()["owner_found"] is False
    assert "*Lead Owner:* UNASSIGNED" in world.alerts()[0]


def test_owner_appears_on_a_later_try(world):
    world.owner_bucket.replies = [MISSING, FOUND]
    world.slack.replies = [SLACK_OK]
    assert world.run(receive_count=1) == FAILED
    assert world.run(receive_count=2) == NO_FAILURES
    assert "*Lead Owner:* Lucija Bitunjac" in world.alerts()[0]


# ---------- failures ----------

def test_slack_failure_releases_marker_so_retry_can_send(world):
    world.owner_bucket.replies = [FOUND, FOUND]
    world.slack.replies = [(404, b"no_service"), SLACK_OK]
    assert world.run() == FAILED
    assert world.marker() is None          # released
    assert world.run(receive_count=2) == NO_FAILURES
    assert world.marker().status == "sent"


def test_missing_source_file_fails(world):
    assert world.run(key=storage.source_key("lead_unknown")) == FAILED


def test_source_file_for_another_lead_fails(world):
    storage.put_json(world.s3, BUCKET, storage.source_key("lead_2"), CRM_EVENT)  # contains lead_1
    assert world.run(key=storage.source_key("lead_2")) == FAILED
    assert world.alerts() == []


# ---------- marker races ----------

def test_another_copy_mid_send_means_retry_later(world):
    world.owner_bucket.replies = [FOUND]
    storage.claim_marker(world.s3, BUCKET, LEAD_ID, NOW - timedelta(seconds=30))
    assert world.run() == FAILED
    assert world.alerts() == []


def test_stale_marker_is_taken_over_and_sent(world):
    world.owner_bucket.replies = [FOUND]
    world.slack.replies = [SLACK_OK]
    storage.claim_marker(world.s3, BUCKET, LEAD_ID, NOW - timedelta(minutes=5))  # crashed copy
    assert world.run() == NO_FAILURES
    assert len(world.alerts()) == 1
    assert world.marker().status == "sent"


# ---------- the real Lambda entry point ----------

def test_handler_end_to_end(world, monkeypatch):
    monkeypatch.setattr(processor, "_s3", world.s3)
    monkeypatch.setattr(processor, "_secrets", world.secrets)
    monkeypatch.setenv("BUCKET_NAME", BUCKET)
    monkeypatch.setenv("OWNER_BASE_URL", world.owner_bucket.url)
    world.owner_bucket.replies = [FOUND]
    world.slack.replies = [SLACK_OK]
    assert processor.handler(sqs_event(), context=None) == NO_FAILURES
    assert len(world.alerts()) == 1
