"""Many leads at the same time: no lost files, no mixed-up owners, no double alerts.

Requirement: "handle many leads in parallel without race conditions". Our design gives
every lead its own files (source/, target/, alerts_sent/ all keyed by lead_id), so
parallel Lambdas never write the same object. These tests run the real receiver and
processor code in 20 threads at once against fake S3/SSM (moto) and fake web servers.
"""

import json
from concurrent.futures import ThreadPoolExecutor

import boto3
import pytest
from moto import mock_aws

from conftest import BUCKET
from fake_http import FakeHttpServer
from leadrelay import processor, receiver, storage
from leadrelay.config import SecretStore, load_settings
from leadrelay.signature import compute_signature

N = 20
KEY = "a1b2c3d4" * 8
NOW_TS = 1_762_860_000
NOW = processor.datetime.fromtimestamp(NOW_TS, processor.timezone.utc)
LEAD_IDS = [f"lead_par{i:02d}" for i in range(N)]


def number(lead_id):
    return lead_id[-2:]  # "lead_par07" -> "07"


def webhook(lead_id):
    raw = json.dumps({"subscription_id": "whsub_1", "event": {
        "object_type": "lead", "action": "created", "lead_id": lead_id,
        "data": {"display_name": f"Person {number(lead_id)}", "status_label": "Potential",
                 "date_created": "2026-11-14T12:00:00+00:00"}}})
    ts = str(NOW_TS)
    return {"httpMethod": "POST", "path": "/crm", "body": raw, "isBase64Encoded": False,
            "headers": {"close-sig-timestamp": ts, "close-sig-hash": compute_signature(KEY, ts, raw)}}


def sqs_event(lead_id, message_id="msg"):
    body = {"Records": [{"s3": {"bucket": {"name": BUCKET},
                                "object": {"key": storage.source_key(lead_id)}}}]}
    return {"Records": [{"messageId": message_id, "body": json.dumps(body),
                         "attributes": {"ApproximateReceiveCount": "1"}}]}


def owner_file(method, path):
    """The fake lookup bucket: lead_parNN gets owner 'Owner NN'."""
    lead_id = path.strip("/").removesuffix(".json")
    return 200, json.dumps({"lead_id": lead_id, "lead_email": f"p{number(lead_id)}@example.com",
                            "lead_owner": f"Owner {number(lead_id)}", "funnel": "F"}).encode()


@pytest.fixture
def world():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        owners, slack = FakeHttpServer(), FakeHttpServer()
        owners.responder = owner_file
        slack.responder = lambda method, path: (200, b"ok")
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/leadrelay/close_signature_key", Value=KEY, Type="SecureString")
        ssm.put_parameter(Name="/leadrelay/slack_webhook_url", Value=slack.url + "/x", Type="SecureString")
        settings = load_settings({"BUCKET_NAME": BUCKET, "OWNER_BASE_URL": owners.url})
        yield s3, SecretStore(ssm), settings, slack
        owners.close()
        slack.close()


def in_parallel(function, items):
    with ThreadPoolExecutor(max_workers=N) as pool:
        return list(pool.map(function, items))


def keys(s3, prefix):
    return sorted(o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", []))


def alert_texts(slack):
    return [json.loads(r["body"])["text"] for r in slack.requests]


def test_20_leads_at_once_give_20_correct_files_and_20_alerts(world):
    s3, secrets, settings, slack = world

    # 1. Close sends 20 webhooks at the same moment.
    replies = in_parallel(lambda lid: receiver.handle(webhook(lid), settings, s3, secrets, now=NOW_TS), LEAD_IDS)
    assert [r["statusCode"] for r in replies] == [200] * N
    assert keys(s3, "source/") == sorted(storage.source_key(lid) for lid in LEAD_IDS)

    # 2. Ten minutes later, 20 processor Lambdas run at the same moment.
    results = in_parallel(lambda lid: processor.handle(sqs_event(lid), settings, s3, secrets, now=NOW), LEAD_IDS)
    assert all(r == {"batchItemFailures": []} for r in results)

    # 3. Every lead has its own enriched file, with its own owner (no mix-ups).
    assert keys(s3, "target/") == sorted(storage.target_key(lid) for lid in LEAD_IDS)
    for lid in LEAD_IDS:
        record = storage.get_json(s3, BUCKET, storage.target_key(lid))
        n = number(lid)
        assert (record["lead_id"], record["display_name"], record["lead_owner"], record["lead_email"]) == \
               (lid, f"Person {n}", f"Owner {n}", f"p{n}@example.com")

    # 4. Exactly one alert per lead, and each alert talks about one lead only.
    texts = alert_texts(slack)
    assert len(texts) == N
    for lid in LEAD_IDS:
        n = number(lid)
        [text] = [t for t in texts if f"*Lead ID:* {lid}" in t]
        assert f"*Name:* Person {n}" in text and f"*Lead Owner:* Owner {n}" in text
    assert all(storage.read_marker(s3, BUCKET, lid).status == "sent" for lid in LEAD_IDS)


def test_same_lead_processed_by_10_lambdas_at_once_alerts_once(world):
    """SQS may deliver one message twice; even 10 copies racing must give one alert."""
    s3, secrets, settings, slack = world
    lid = LEAD_IDS[0]
    receiver.handle(webhook(lid), settings, s3, secrets, now=NOW_TS)

    in_parallel(lambda i: processor.handle(sqs_event(lid, f"msg-{i}"), settings, s3, secrets, now=NOW), range(10))

    # Copies that lose the race either see "sent" or retry later; either way, one alert.
    assert len(alert_texts(slack)) == 1
    assert storage.read_marker(s3, BUCKET, lid).status == "sent"
