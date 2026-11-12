"""Run LeadRelay end to end on this Mac, with no AWS and no internet.

    .venv/bin/python scripts/demo_local.py

Fakes: S3 and SSM (moto, in memory), the owner bucket and Slack (small web
servers on 127.0.0.1). The real receiver and processor code runs unchanged.
The 10-minute SQS delay is skipped: we hand the processor the message at once.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ[name] = "demo"  # fake keys: this script can never touch a real account
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

from fake_http import FakeHttpServer  # noqa: E402
from leadrelay import processor, receiver, storage  # noqa: E402
from leadrelay.config import SecretStore, load_settings  # noqa: E402
from leadrelay.signature import compute_signature  # noqa: E402

BUCKET = "leadrelay-demo"
SIGNING_KEY = "ab" * 32
START = datetime.now(timezone.utc)


def title(text):
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


def show(label, data):
    print(f"--- {label}")
    print(data if isinstance(data, str) else json.dumps(data, indent=2))


def webhook(lead_id, name):
    """The API Gateway event Close would cause, signed like Close signs it."""
    body = json.dumps({
        "subscription_id": "whsub_demo",
        "event": {
            "object_type": "lead", "action": "created", "lead_id": lead_id,
            "data": {"display_name": name, "status_label": "Potential",
                     "date_created": START.isoformat()},
        },
    })
    ts = str(int(START.timestamp()))
    return {"headers": {"Close-Sig-Timestamp": ts, "Close-Sig-Hash": compute_signature(SIGNING_KEY, ts, body)},
            "body": body, "isBase64Encoded": False}


def sqs_message(lead_id, receive_count):
    """What SQS would deliver 10 minutes later: the S3 notification for the source file."""
    notification = {"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Put",
                                 "s3": {"bucket": {"name": BUCKET},
                                        "object": {"key": storage.source_key(lead_id)}}}]}
    return {"Records": [{"messageId": f"{lead_id}-try{receive_count}", "body": json.dumps(notification),
                         "attributes": {"ApproximateReceiveCount": str(receive_count)}}]}


def main():
    # Show the code's own log lines, the way CloudWatch would collect them.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="    [log %(levelname)s] %(message)s")
    for noisy in ("botocore", "boto3", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    owner_bucket, slack = FakeHttpServer(), FakeHttpServer()
    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=BUCKET)
        ssm = boto3.client("ssm")
        ssm.put_parameter(Name="/leadrelay/close_signature_key", Value=SIGNING_KEY, Type="SecureString")
        ssm.put_parameter(Name="/leadrelay/slack_webhook_url", Value=slack.url + "/services/demo", Type="SecureString")
        settings = load_settings({"BUCKET_NAME": BUCKET, "OWNER_BASE_URL": owner_bucket.url})
        secrets = SecretStore(ssm)

        def run_processor(lead_id, try_number):
            now = START + timedelta(minutes=10 + 5 * (try_number - 1))
            result = processor.handle(sqs_message(lead_id, try_number), settings, s3, secrets, now=now)
            outcome = "retry later" if result["batchItemFailures"] else "done"
            print(f"processor, try {try_number} (minute {10 + 5 * (try_number - 1)}): {outcome}")

        def new_slack_messages(seen=[0]):
            new = slack.requests[seen[0]:]
            seen[0] = len(slack.requests)
            return [json.loads(r["body"])["text"] for r in new]

        # ---------------------------------------------------------------
        title("1. Lead A arrives; its owner is assigned within 10 minutes")
        reply = receiver.handle(webhook("lead_demoA", "Adam Capozzoli"), settings, s3, secrets)
        print(f"receiver replied to Close: {reply['statusCode']} {reply['body']}")
        show("source/crm_event_lead_demoA.json", storage.get_json(s3, BUCKET, storage.source_key("lead_demoA")))

        print("\n... SQS keeps the message hidden for 10 minutes (skipped in this demo) ...\n")
        owner_bucket.replies = [(200, json.dumps({
            "lead_id": "lead_demoA", "lead_email": "adam@example.com",
            "lead_owner": "Lucija Bitunjac", "funnel": "DE ACADEMY Direct VSL"}).encode())]
        slack.replies = [(200, b"ok")]
        run_processor("lead_demoA", 1)
        show("target/enriched_lead_demoA.json", storage.get_json(s3, BUCKET, storage.target_key("lead_demoA")))
        for text in new_slack_messages():
            show("Slack message", text)

        # ---------------------------------------------------------------
        title("2. The same message arrives again (SQS can deliver twice)")
        owner_bucket.replies = [(200, json.dumps({
            "lead_id": "lead_demoA", "lead_email": "adam@example.com",
            "lead_owner": "Lucija Bitunjac", "funnel": "DE ACADEMY Direct VSL"}).encode())]
        run_processor("lead_demoA", 2)
        print(f"new Slack messages: {len(new_slack_messages())}  (marker alerts_sent/lead_demoA says 'sent')")

        # ---------------------------------------------------------------
        title("3. Lead B arrives; its owner never shows up")
        receiver.handle(webhook("lead_demoB", "Lowell Bast"), settings, s3, secrets)
        print("receiver saved source/crm_event_lead_demoB.json")
        for try_number in range(1, 7):
            owner_bucket.replies = [(403, b"")]  # S3 says 403 for a file that is not there
            slack.replies = [(200, b"ok")]
            run_processor("lead_demoB", try_number)
        for text in new_slack_messages():
            show("Slack message", text)

        # ---------------------------------------------------------------
        title("4. A forged webhook (wrong key)")
        forged = webhook("lead_demoC", "Mallory")
        forged["headers"]["Close-Sig-Hash"] = "0" * 64
        reply = receiver.handle(forged, settings, s3, secrets)
        print(f"receiver replied: {reply['statusCode']} {reply['body']}")

        title("Bucket contents at the end")
        for obj in s3.list_objects_v2(Bucket=BUCKET)["Contents"]:
            print(obj["Key"])

    owner_bucket.close()
    slack.close()


if __name__ == "__main__":
    main()
