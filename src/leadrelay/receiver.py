"""Receiver Lambda: Close webhook in -> source/crm_event_{lead_id}.json out.

API Gateway (HTTP API, payload format 1.0) calls handler() once per webhook.
Close needs an answer within 15 s, so this does only quick work:
verify -> parse -> filter -> save. The slow part waits in the queue.

    Situation                                  Reply
    saved                                      200
    not a lead "created" event                 200 (ignored, so Close does not retry)
    bad / missing / old signature              401 (nothing saved)
    body not JSON, or lead_id missing/invalid  400 (nothing saved)
    S3 write or configuration fails            500 (Close retries for up to 72 h)
"""

import base64
import json
import logging
import time

import boto3

from leadrelay import storage
from leadrelay.config import SecretStore, load_settings
from leadrelay.signature import is_valid_signature

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Created once per Lambda container and reused by every invocation in it.
_s3 = None
_secrets = None


def handler(event, context):
    """Entry point AWS Lambda calls."""
    global _s3, _secrets
    try:
        settings = load_settings()
        if _s3 is None:
            _s3 = boto3.client("s3")
            _secrets = SecretStore(boto3.client("ssm"))
        return handle(event, settings, _s3, _secrets)
    except Exception:
        log.exception("receiver failed", extra={"step": "receive"})
        return _reply(500, "internal error")


def handle(event, settings, s3, secrets, now=None) -> dict:
    """The real work, with every dependency passed in (so tests can pass fakes)."""
    raw_body = _raw_body(event)
    if raw_body is None:
        log.error("request has no body", extra={"step": "receive"})
        return _reply(400, "missing body")

    # 1. Signature first, on the body exactly as received.
    headers = {name.lower(): value for name, value in (event.get("headers") or {}).items()}
    def signature_ok(key):
        return is_valid_signature(key, headers.get("close-sig-timestamp"),
                                  headers.get("close-sig-hash"), raw_body, now=now)

    if not signature_ok(secrets.get(settings.signature_key_param)):
        # Maybe the key was rotated in SSM after this container cached it:
        # re-read it once (rate-limited inside SecretStore) and check again.
        if not (secrets.refresh(settings.signature_key_param)
                and signature_ok(secrets.get(settings.signature_key_param))):
            log.warning("bad signature, request rejected", extra={"step": "receive"})
            return _reply(401, "invalid signature")
        log.info("signature key reloaded from SSM", extra={"step": "receive"})

    # 2. Parse.
    try:
        body = json.loads(raw_body)
        close_event = body["event"]
        object_type = close_event.get("object_type")
        action = close_event.get("action")
    except (ValueError, KeyError, TypeError, AttributeError):
        log.error("body is not a Close webhook event", extra={"step": "receive"})
        return _reply(400, "body is not a Close event")

    # 3. Filter: only new leads.
    if object_type != "lead" or action != "created":
        log.info("event ignored", extra={"step": "receive", "object_type": object_type, "action": action})
        return _reply(200, "ignored")

    lead_id = close_event.get("lead_id")
    try:
        key_name = storage.source_key(lead_id)  # also refuses unsafe lead_ids
    except ValueError:
        log.error("missing or invalid lead_id", extra={"step": "receive"})
        return _reply(400, "missing or invalid lead_id")

    # 4. Save the parsed body (subscription_id + event), not the API Gateway wrapper.
    storage.put_json(s3, settings.bucket_name, key_name, body)
    log.info("lead saved", extra={"step": "receive", "lead_id": lead_id, "key": key_name})
    return _reply(200, "saved")


def _raw_body(event) -> str | None:
    body = event.get("body")
    if body is None:
        return None
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return body


def _reply(status: int, message: str) -> dict:
    """The response shape API Gateway expects back from Lambda."""
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": message}),
    }
