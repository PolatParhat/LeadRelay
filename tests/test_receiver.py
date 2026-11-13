"""Tests for the receiver Lambda: fake S3 and SSM (moto), signed fake webhooks."""

import base64
import json

import boto3
import pytest
from moto import mock_aws

from conftest import BUCKET
from leadrelay import receiver, storage
from leadrelay.config import SecretStore, load_settings
from leadrelay.signature import compute_signature

KEY = "a1b2c3d4" * 8
NOW = 1_762_860_000
LEAD_ID = "lead_Q6uqUbqVS4NYyHGJnfxpfNKpZ0roxEDCdD9oIAaMJ4z"
BODY = {
    "subscription_id": "whsub_1Lr0LeQ56WDreQtJNiuUAr",
    "event": {
        "object_type": "lead", "action": "created", "lead_id": LEAD_ID,
        "data": {"display_name": "Adam Capozzoli", "status_label": "Potential",
                 "date_created": "2025-09-04T07:27:17.642000+00:00"},
    },
}


def webhook(body=BODY, key=KEY, ts=str(NOW), base64_encoded=False, header_case=str):
    """An API Gateway event as Close would cause it, signed with `key`."""
    raw = body if isinstance(body, str) else json.dumps(body)
    headers = {
        header_case("Close-Sig-Timestamp"): ts,
        header_case("Close-Sig-Hash"): compute_signature(key, ts, raw),
        "content-type": "application/json",
    }
    if base64_encoded:
        raw = base64.b64encode(raw.encode()).decode()
    return {"httpMethod": "POST", "path": "/crm", "headers": headers,
            "body": raw, "isBase64Encoded": base64_encoded}


@pytest.fixture
def aws():
    """Fake S3 bucket + fake SSM secret, and the settings pointing at them."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/leadrelay/close_signature_key", Value=KEY, Type="SecureString")
        yield s3, SecretStore(ssm), load_settings({"BUCKET_NAME": BUCKET})


def call(aws, event):
    s3, secrets, settings = aws
    reply = receiver.handle(event, settings, s3, secrets, now=NOW)
    return reply["statusCode"], json.loads(reply["body"])["message"]


def saved_keys(aws):
    s3 = aws[0]
    return [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])]


def test_new_lead_is_saved_unchanged(aws):
    assert call(aws, webhook()) == (200, "saved")
    assert storage.get_json(aws[0], BUCKET, storage.source_key(LEAD_ID)) == BODY


def test_base64_body_is_decoded(aws):
    assert call(aws, webhook(base64_encoded=True)) == (200, "saved")


def test_header_names_in_any_case_work(aws):
    assert call(aws, webhook(header_case=str.lower)) == (200, "saved")


def test_same_webhook_twice_keeps_one_file(aws):
    call(aws, webhook())
    call(aws, webhook())
    assert saved_keys(aws) == [storage.source_key(LEAD_ID)]


def test_bad_signature_is_401_and_saves_nothing(aws):
    assert call(aws, webhook(key="ff" * 32)) == (401, "invalid signature")
    assert saved_keys(aws) == []


def test_old_timestamp_is_401(aws):
    assert call(aws, webhook(ts=str(NOW - 600))) == (401, "invalid signature")


def test_missing_signature_headers_is_401(aws):
    event = webhook()
    event["headers"] = {"content-type": "application/json"}
    assert call(aws, event)[0] == 401


@pytest.mark.parametrize("change", [{"action": "updated"}, {"object_type": "contact"}])
def test_other_events_are_ignored_with_200(aws, change):
    body = {**BODY, "event": {**BODY["event"], **change}}
    assert call(aws, webhook(body)) == (200, "ignored")
    assert saved_keys(aws) == []


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", '{"no_event": 1}'])
def test_body_that_is_not_a_close_event_is_400(aws, raw):
    assert call(aws, webhook(raw))[0] == 400


@pytest.mark.parametrize("lead_id", [None, "../evil"])
def test_missing_or_unsafe_lead_id_is_400(aws, lead_id):
    body = {**BODY, "event": {**BODY["event"], "lead_id": lead_id}}
    assert call(aws, webhook(body)) == (400, "missing or invalid lead_id")
    assert saved_keys(aws) == []


def test_missing_body_is_400(aws):
    event = webhook()
    del event["body"]
    assert call(aws, event)[0] == 400


# ---------- the real Lambda entry point ----------

@pytest.fixture
def fresh_receiver(monkeypatch):
    """Forget clients cached by earlier tests (like a new Lambda container)."""
    monkeypatch.setattr(receiver, "_s3", None)
    monkeypatch.setattr(receiver, "_secrets", None)


def test_handler_end_to_end(aws, monkeypatch, fresh_receiver):
    monkeypatch.setenv("BUCKET_NAME", BUCKET)
    monkeypatch.setattr("leadrelay.signature.time.time", lambda: NOW)
    reply = receiver.handler(webhook(), context=None)
    assert reply["statusCode"] == 200
    assert saved_keys(aws) == [storage.source_key(LEAD_ID)]


def test_handler_returns_500_when_s3_fails(aws, monkeypatch, fresh_receiver):
    monkeypatch.setenv("BUCKET_NAME", "bucket-that-does-not-exist")
    monkeypatch.setattr("leadrelay.signature.time.time", lambda: NOW)
    assert receiver.handler(webhook(), context=None)["statusCode"] == 500


def test_handler_returns_500_when_config_missing(monkeypatch, fresh_receiver):
    monkeypatch.delenv("BUCKET_NAME", raising=False)
    assert receiver.handler(webhook(), context=None)["statusCode"] == 500
