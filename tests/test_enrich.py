"""Tests for leadrelay.enrich (pure functions: no AWS, no network)."""

import copy
from datetime import datetime, timezone

import pytest

from leadrelay.enrich import InvalidLeadEvent, build_enriched_record, extract_lead

# Shortened copy of the sample stored event in the requirements doc.
CRM_EVENT = {
    "subscription_id": "whsub_1zwvQVQOBPFqrH6xXJEvFJ",
    "event": {
        "id": "ev_1ntH1vAE4G7DNjNZYkMeck",
        "date_created": "2025-05-20T12:14:56.446000",  # when the EVENT happened (not used)
        "object_type": "lead",
        "lead_id": "lead_niuYPXlw6vnFQIhwZCKDaaKv9XMQs9KA5NgxhNRBgaA",
        "action": "created",
        "data": {
            "display_name": "Lowell Bast",
            "status_label": "Potential",
            "date_created": "2025-05-20T12:14:56.409000+00:00",  # when the LEAD was created (used)
            "created_by_name": "Christopher Garzon",
        },
    },
}
OWNER = {"lead_email": "lowell@example.com", "lead_owner": "Lucija Bitunjac", "funnel": "DE ACADEMY Direct VSL"}
NOW = datetime(2026, 11, 11, 12, 40, tzinfo=timezone.utc)
SOURCE_KEY = "source/crm_event_lead_niuYPXlw6vnFQIhwZCKDaaKv9XMQs9KA5NgxhNRBgaA.json"


def test_extract_lead_picks_the_four_crm_fields():
    assert extract_lead(CRM_EVENT) == {
        "lead_id": "lead_niuYPXlw6vnFQIhwZCKDaaKv9XMQs9KA5NgxhNRBgaA",
        "display_name": "Lowell Bast",
        "date_created": "2025-05-20T12:14:56.409000+00:00",
        "status_label": "Potential",
    }


@pytest.mark.parametrize("field", ["display_name", "date_created", "status_label"])
def test_missing_data_field_is_named_in_the_error(field):
    event = copy.deepcopy(CRM_EVENT)
    del event["event"]["data"][field]
    with pytest.raises(InvalidLeadEvent, match=field):
        extract_lead(event)


def test_missing_lead_id_raises():
    event = copy.deepcopy(CRM_EVENT)
    del event["event"]["lead_id"]
    with pytest.raises(InvalidLeadEvent, match="lead_id"):
        extract_lead(event)


@pytest.mark.parametrize("broken", [{}, {"event": "text"}, {"event": {"lead_id": "lead_1"}}])
def test_wrong_shape_raises(broken):
    with pytest.raises(InvalidLeadEvent):
        extract_lead(broken)


def test_enriched_record_with_owner():
    record = build_enriched_record(extract_lead(CRM_EVENT), OWNER, SOURCE_KEY, NOW)
    assert record == {
        "lead_id": "lead_niuYPXlw6vnFQIhwZCKDaaKv9XMQs9KA5NgxhNRBgaA",
        "display_name": "Lowell Bast",
        "date_created": "2025-05-20T12:14:56.409000+00:00",
        "status_label": "Potential",
        "lead_email": "lowell@example.com",
        "lead_owner": "Lucija Bitunjac",
        "funnel": "DE ACADEMY Direct VSL",
        "owner_found": True,
        "enriched_at": "2026-11-11T12:40:00+00:00",
        "source_key": SOURCE_KEY,
    }


def test_enriched_record_without_owner_file():
    record = build_enriched_record(extract_lead(CRM_EVENT), None, SOURCE_KEY, NOW)
    assert record["owner_found"] is False
    assert record["lead_owner"] is None and record["lead_email"] is None and record["funnel"] is None
    assert record["display_name"] == "Lowell Bast"  # CRM fields still there


def test_owner_file_with_empty_owner_counts_as_not_found():
    record = build_enriched_record(extract_lead(CRM_EVENT), {**OWNER, "lead_owner": ""}, SOURCE_KEY, NOW)
    assert record["owner_found"] is False
    assert record["lead_email"] == "lowell@example.com"  # keep what the file did give us


def test_inputs_are_not_changed():
    lead = extract_lead(CRM_EVENT)
    before = dict(lead)
    build_enriched_record(lead, OWNER, SOURCE_KEY, NOW)
    assert lead == before
