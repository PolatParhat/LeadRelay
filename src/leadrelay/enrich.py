"""Merge the CRM event and the owner lookup into one flat enriched record.

Pure functions: no S3, no network, no clock (the time is passed in). That makes
this the easiest module to test, and the processor just wires it together.

Where each field comes from (the requirements say so):
    CRM event  -> lead_id, display_name, date_created, status_label
    lookup     -> lead_email, lead_owner, funnel
"""

from datetime import datetime


class InvalidLeadEvent(ValueError):
    """The stored CRM event is missing something we need. Retrying will not fix it."""


_EVENT_FIELDS = ("display_name", "date_created", "status_label")  # inside event["data"]
_OWNER_FIELDS = ("lead_email", "lead_owner", "funnel")


def extract_lead(crm_event: dict) -> dict:
    """Pick the 4 CRM fields out of the stored webhook body.

    crm_event is the file source/crm_event_{lead_id}.json:
        {"subscription_id": ..., "event": {"lead_id": ..., "data": {"display_name": ..., ...}}}
    """
    event = crm_event.get("event")
    if not isinstance(event, dict):
        raise InvalidLeadEvent("no 'event' object in the CRM event")

    data = event.get("data")
    if not isinstance(data, dict):
        raise InvalidLeadEvent("no 'event.data' object in the CRM event")

    lead = {"lead_id": event.get("lead_id")}
    for field in _EVENT_FIELDS:
        lead[field] = data.get(field)

    missing = [name for name, value in lead.items() if value is None]
    if missing:
        raise InvalidLeadEvent(f"CRM event is missing: {', '.join(missing)}")
    return lead


def build_enriched_record(lead: dict, owner: dict | None, source_key: str, now: datetime) -> dict:
    """Combine lead (from extract_lead) and owner (from lookup.fetch_owner, or None).

    owner_found is True only if we got a file AND it names an owner. When it is
    False the owner fields stay None here; the alert shows "UNASSIGNED".
    """
    owner = owner or {}
    record = dict(lead)
    for field in _OWNER_FIELDS:
        record[field] = owner.get(field)
    record["owner_found"] = bool(owner.get("lead_owner"))
    record["enriched_at"] = now.isoformat()
    record["source_key"] = source_key
    return record
