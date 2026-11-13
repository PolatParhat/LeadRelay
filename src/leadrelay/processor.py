"""Processor Lambda: SQS message (10 min after the lead arrived) -> lookup -> target/ -> Slack.

SQS calls handler() with a batch of messages (batch size 1 in our setup). Each
message body is the S3 event notification for one new source/ file.

For each message:
    1. find the lead_id from the S3 key (skip S3's one-time test message)
    2. read source/crm_event_{lead_id}.json and pick the CRM fields
    3. look up the owner
    4. owner missing: tries 1-5 -> retry later; try 6 -> continue as UNASSIGNED
    5. write target/enriched_{lead_id}.json
    6. send the Slack alert exactly once (alerts_sent/{lead_id} marker)

A message that fails is reported back to SQS ("batchItemFailures"); SQS shows it
again after the visibility timeout (5 min) and after 10 failures moves it to the DLQ.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus

import boto3

from leadrelay import storage
from leadrelay.alert import send_alert
from leadrelay.config import SecretStore, load_settings
from leadrelay.enrich import build_enriched_record, extract_lead
from leadrelay.lookup import fetch_owner

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

_s3 = None
_secrets = None


class RetryLater(Exception):
    """Not an error: the message should simply come back later (owner not there yet,
    or another copy is sending this lead's alert right now)."""


# ---------- Lambda entry point ----------

def handler(event, context):
    global _s3, _secrets
    settings = load_settings()
    if _s3 is None:
        _s3 = boto3.client("s3")
        _secrets = SecretStore(boto3.client("ssm"))
    return handle(event, settings, _s3, _secrets)


def handle(event, settings, s3, secrets, now=None) -> dict:
    """Process every message; tell SQS which ones failed so only those come back."""
    failures = []
    for message in event.get("Records", []):
        message_id = message.get("messageId")
        try:
            process_message(message, settings, s3, secrets, now or datetime.now(timezone.utc))
        except RetryLater as reason:
            log.info("will retry later", extra={"step": "process", "message_id": message_id, "reason": str(reason)})
            failures.append({"itemIdentifier": message_id})
        except Exception:
            log.exception("message failed", extra={"step": "process", "message_id": message_id})
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


# ---------- one message ----------

def process_message(message, settings, s3, secrets, now: datetime) -> None:
    notification = json.loads(message["body"])
    if notification.get("Event") == "s3:TestEvent":
        log.info("S3 test event ignored", extra={"step": "process"})
        return

    receive_count = int(message["attributes"]["ApproximateReceiveCount"])
    for s3_record in notification["Records"]:
        key = unquote_plus(s3_record["s3"]["object"]["key"])  # S3 URL-encodes keys in events
        process_lead(key, receive_count, settings, s3, secrets, now)


def process_lead(key, receive_count, settings, s3, secrets, now: datetime) -> None:
    bucket = settings.bucket_name
    lead_id = storage.lead_id_from_source_key(key)
    ctx = {"lead_id": lead_id, "try": receive_count}

    # 1. The raw event, saved by the receiver.
    lead = extract_lead(storage.get_json(s3, bucket, key))
    if lead["lead_id"] != lead_id:
        raise ValueError(f"{key} contains lead {lead['lead_id']}")

    # 2. The owner (only now, 10+ minutes after the lead arrived).
    owner = fetch_owner(lead_id, base_url=settings.owner_base_url)
    owner_found = bool(owner and owner.get("lead_owner"))
    log.info("owner lookup done", extra={**ctx, "step": "lookup", "owner_found": owner_found})

    # 3. Missing-owner policy: retry until the last try, then alert as UNASSIGNED.
    if not owner_found:
        if receive_count < settings.owner_max_tries:
            raise RetryLater(f"owner of {lead_id} not assigned yet (try {receive_count} of {settings.owner_max_tries})")
        log.warning("owner still missing, alerting as UNASSIGNED", extra={**ctx, "step": "lookup"})

    # 4. The enriched record.
    record = build_enriched_record(lead, owner, key, now)
    storage.put_json(s3, bucket, storage.target_key(lead_id), record)
    log.info("enriched record saved", extra={**ctx, "step": "enrich"})

    # 5. The alert, once.
    send_once(s3, bucket, record, lambda: secrets.get(settings.slack_webhook_param),
              now, settings.marker_stale_seconds)


# ---------- exactly-once alert ----------

def send_once(s3, bucket, record, get_webhook_url, now: datetime, stale_seconds: int) -> None:
    """The marker protocol from docs/architecture.md section 4."""
    lead_id = record["lead_id"]

    if not storage.claim_marker(s3, bucket, lead_id, now):
        marker = storage.read_marker(s3, bucket, lead_id)
        if marker is None:
            raise RetryLater(f"marker of {lead_id} changed while reading it")
        if marker.status == "sent":
            log.info("alert already sent, duplicate skipped", extra={"lead_id": lead_id, "step": "alert"})
            return
        if now - marker.at < timedelta(seconds=stale_seconds):
            raise RetryLater(f"another copy is sending the alert for {lead_id}")
        if not storage.take_over_marker(s3, bucket, lead_id, marker.etag, now):
            raise RetryLater(f"another copy took over the alert for {lead_id}")
        log.warning("took over a stale alert marker", extra={"lead_id": lead_id, "step": "alert"})

    # We own the marker: send, then record it as sent.
    try:
        send_alert(get_webhook_url(), record)
    except Exception:
        storage.release_marker(s3, bucket, lead_id)  # let the retry claim it again
        raise
    storage.mark_sent(s3, bucket, lead_id, now)
