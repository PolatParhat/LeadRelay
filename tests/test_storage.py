"""Tests for leadrelay.storage, against moto's fake S3 (no real AWS)."""

from datetime import datetime, timedelta, timezone

import pytest

from conftest import BUCKET
from leadrelay import storage

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


# ---------- key names ----------

def test_key_names_follow_the_agreed_layout():
    assert storage.source_key("lead_123") == "source/crm_event_lead_123.json"
    assert storage.target_key("lead_123") == "target/enriched_lead_123.json"
    assert storage.marker_key("lead_123") == "alerts_sent/lead_123"


def test_lead_id_from_source_key_round_trips():
    key = storage.source_key("lead_Q6uqX1")
    assert storage.lead_id_from_source_key(key) == "lead_Q6uqX1"


@pytest.mark.parametrize("bad", ["", "../evil", "lead/123", "lead 123", None])
def test_unsafe_lead_ids_are_refused(bad):
    with pytest.raises(ValueError):
        storage.source_key(bad)


@pytest.mark.parametrize("key", ["target/enriched_lead_1.json", "source/other_lead_1.json", "source/crm_event_.json"])
def test_non_source_keys_are_refused(key):
    with pytest.raises(ValueError):
        storage.lead_id_from_source_key(key)


# ---------- JSON files ----------

def test_put_then_get_returns_the_same_data(s3):
    data = {"lead_id": "lead_1", "display_name": "Zoë Müller"}  # non-English letters survive
    storage.put_json(s3, BUCKET, "target/enriched_lead_1.json", data)
    assert storage.get_json(s3, BUCKET, "target/enriched_lead_1.json") == data


def test_writing_twice_keeps_one_file(s3):
    storage.put_json(s3, BUCKET, storage.source_key("lead_1"), {"v": 1})
    storage.put_json(s3, BUCKET, storage.source_key("lead_1"), {"v": 2})
    listing = s3.list_objects_v2(Bucket=BUCKET, Prefix="source/")
    assert listing["KeyCount"] == 1
    assert storage.get_json(s3, BUCKET, storage.source_key("lead_1")) == {"v": 2}


def test_get_missing_file_raises(s3):
    with pytest.raises(s3.exceptions.NoSuchKey):
        storage.get_json(s3, BUCKET, storage.source_key("lead_missing"))


# ---------- alert marker ----------

def test_first_claim_wins_second_loses(s3):
    assert storage.claim_marker(s3, BUCKET, "lead_1", NOW) is True
    assert storage.claim_marker(s3, BUCKET, "lead_1", NOW) is False


def test_claims_for_different_leads_do_not_interfere(s3):
    assert storage.claim_marker(s3, BUCKET, "lead_1", NOW) is True
    assert storage.claim_marker(s3, BUCKET, "lead_2", NOW) is True


def test_read_marker_shows_status_and_time(s3):
    assert storage.read_marker(s3, BUCKET, "lead_1") is None
    storage.claim_marker(s3, BUCKET, "lead_1", NOW)
    marker = storage.read_marker(s3, BUCKET, "lead_1")
    assert marker.status == "sending"
    assert marker.at == NOW


def test_mark_sent_changes_status(s3):
    storage.claim_marker(s3, BUCKET, "lead_1", NOW)
    storage.mark_sent(s3, BUCKET, "lead_1", NOW + timedelta(seconds=1))
    assert storage.read_marker(s3, BUCKET, "lead_1").status == "sent"


def test_release_lets_the_retry_claim_again(s3):
    storage.claim_marker(s3, BUCKET, "lead_1", NOW)
    storage.release_marker(s3, BUCKET, "lead_1")
    assert storage.claim_marker(s3, BUCKET, "lead_1", NOW) is True


def test_only_one_copy_can_take_over_a_stale_marker(s3):
    storage.claim_marker(s3, BUCKET, "lead_1", NOW)
    stale = storage.read_marker(s3, BUCKET, "lead_1")
    later = NOW + timedelta(minutes=3)
    # two copies both read the same stale marker, then both try to take over
    assert storage.take_over_marker(s3, BUCKET, "lead_1", stale.etag, later) is True
    assert storage.take_over_marker(s3, BUCKET, "lead_1", stale.etag, later) is False
