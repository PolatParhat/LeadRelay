"""Everything LeadRelay reads from or writes to its S3 bucket.

One bucket, three prefixes (folders):
    source/crm_event_{lead_id}.json   raw webhook body      (written by the receiver)
    target/enriched_{lead_id}.json    enriched record       (written by the processor)
    alerts_sent/{lead_id}             "alert sent" marker   (written by the processor)

Every function takes the S3 client as its first argument. In Lambda we pass a
real boto3 client; in tests we pass one faked by moto. Same code, no AWS needed.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime

from botocore.exceptions import ClientError

SOURCE_PREFIX = "source/"
_SOURCE_NAME = "crm_event_"
_LEAD_ID = re.compile(r"^[A-Za-z0-9_]+$")  # e.g. lead_Q6uqX1...; no "/" or ".." allowed

# S3 error codes meaning "your conditional write lost" (412, or 409 while another write is in flight).
_CONDITION_LOST = {"PreconditionFailed", "ConditionalRequestConflict"}


# ---------- key names ----------

def _check_lead_id(lead_id: str) -> str:
    """Refuse odd lead_ids so nobody can write outside our prefixes (e.g. "../x")."""
    if not isinstance(lead_id, str) or not _LEAD_ID.match(lead_id):
        raise ValueError(f"invalid lead_id: {lead_id!r}")
    return lead_id


def source_key(lead_id: str) -> str:
    return f"{SOURCE_PREFIX}{_SOURCE_NAME}{_check_lead_id(lead_id)}.json"


def target_key(lead_id: str) -> str:
    return f"target/enriched_{_check_lead_id(lead_id)}.json"


def marker_key(lead_id: str) -> str:
    return f"alerts_sent/{_check_lead_id(lead_id)}"


def lead_id_from_source_key(key: str) -> str:
    """source/crm_event_lead_123.json -> lead_123 (used by the processor)."""
    start = SOURCE_PREFIX + _SOURCE_NAME
    if not (key.startswith(start) and key.endswith(".json")):
        raise ValueError(f"not a source key: {key!r}")
    return _check_lead_id(key[len(start):-len(".json")])


# ---------- JSON files ----------

def put_json(s3, bucket: str, key: str, data: dict) -> None:
    """Write a dict as a JSON file. Same key again = overwrite (still one file)."""
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def get_json(s3, bucket: str, key: str) -> dict:
    """Read a JSON file into a dict. A missing file raises (the caller should fail loudly)."""
    response = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read())


# ---------- alert marker (exactly-once alerts) ----------

@dataclass
class Marker:
    status: str      # "sending" or "sent"
    at: datetime     # when that status was written
    etag: str        # S3's version fingerprint of the marker file, used for take-over


def _marker_body(status: str, now: datetime) -> bytes:
    return json.dumps({"status": status, "at": now.isoformat()}).encode("utf-8")


def claim_marker(s3, bucket: str, lead_id: str, now: datetime) -> bool:
    """Try to create the marker as "sending". True = we won and must send the alert.

    IfNoneMatch="*" tells S3: write only if no file exists at this key. If two
    copies of the same lead race, S3 lets exactly one of them win.
    """
    try:
        s3.put_object(
            Bucket=bucket, Key=marker_key(lead_id),
            Body=_marker_body("sending", now), IfNoneMatch="*",
        )
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] in _CONDITION_LOST:
            return False
        raise


def read_marker(s3, bucket: str, lead_id: str) -> Marker | None:
    """Return the current marker, or None if there is none."""
    try:
        response = s3.get_object(Bucket=bucket, Key=marker_key(lead_id))
    except ClientError as error:
        if error.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise
    data = json.loads(response["Body"].read())
    return Marker(
        status=data["status"],
        at=datetime.fromisoformat(data["at"]),
        etag=response["ETag"],
    )


def take_over_marker(s3, bucket: str, lead_id: str, old_etag: str, now: datetime) -> bool:
    """Replace a stale "sending" marker (its sender crashed). True = we took over.

    IfMatch=old_etag tells S3: write only if the file is still exactly the one we
    read. If another copy took over first, the ETag changed and we lose.
    """
    try:
        s3.put_object(
            Bucket=bucket, Key=marker_key(lead_id),
            Body=_marker_body("sending", now), IfMatch=old_etag,
        )
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] in _CONDITION_LOST:
            return False
        raise


def mark_sent(s3, bucket: str, lead_id: str, now: datetime) -> None:
    """After Slack accepted the alert: marker becomes "sent" for good."""
    s3.put_object(Bucket=bucket, Key=marker_key(lead_id), Body=_marker_body("sent", now))


def release_marker(s3, bucket: str, lead_id: str) -> None:
    """Slack failed: delete our claim so the retry can claim it again."""
    s3.delete_object(Bucket=bucket, Key=marker_key(lead_id))
