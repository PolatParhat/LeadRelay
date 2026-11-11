"""Fetch a lead's owner details from the public dea-lead-owner bucket.

The file is public, so a plain HTTPS GET is enough (no AWS credentials needed):
    https://dea-lead-owner.s3.us-east-1.amazonaws.com/{lead_id}.json

Three possible outcomes:
    found      -> a dict with lead_email, lead_owner, funnel
    not there  -> None (403/404: the CRM has not written the owner file yet)
    broken     -> LookupError raised (network trouble that retries did not fix,
                  or a file that is not what we expect)
"""

import json
import logging
import time
import urllib.error
import urllib.request

OWNER_BASE_URL = "https://dea-lead-owner.s3.us-east-1.amazonaws.com"
TIMEOUT_SECONDS = 5
ATTEMPTS = 3  # first try + 2 retries, waiting 1 s then 2 s

# S3 answers 403 (not 404) for a missing file when the bucket does not allow listing.
_NOT_THERE = {403, 404}
_OWNER_FIELDS = ("lead_email", "lead_owner", "funnel")

log = logging.getLogger(__name__)


class OwnerLookupError(Exception):
    """The lookup failed in a way that retrying right now did not fix."""


def fetch_owner(
    lead_id: str,
    base_url: str = OWNER_BASE_URL,
    timeout: float = TIMEOUT_SECONDS,
    attempts: int = ATTEMPTS,
    sleep=time.sleep,
) -> dict | None:
    """Return the owner fields for lead_id, or None if the file is not there yet.

    `base_url` and `sleep` can be swapped in tests (local fake server, no waiting).
    """
    url = f"{base_url}/{lead_id}.json"

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                raw = response.read()
            return _parse_owner(lead_id, raw)

        except urllib.error.HTTPError as error:   # the server answered with an error code
            if error.code in _NOT_THERE:
                log.info("owner file not there yet", extra={"lead_id": lead_id, "status": error.code})
                return None
            if error.code < 500:                  # other 4xx: retrying will not help
                raise OwnerLookupError(f"lookup for {lead_id} got HTTP {error.code}") from error
            problem = f"HTTP {error.code}"        # 5xx: server trouble, worth retrying

        except (urllib.error.URLError, TimeoutError) as error:  # no answer at all
            problem = f"network error: {error}"

        if attempt < attempts:
            wait = 2 ** (attempt - 1)             # 1 s, 2 s, 4 s, ... (exponential backoff)
            log.warning("lookup failed, retrying", extra={"lead_id": lead_id, "problem": problem, "wait_s": wait})
            sleep(wait)

    raise OwnerLookupError(f"lookup for {lead_id} failed after {attempts} attempts: {problem}")


def _parse_owner(lead_id: str, raw: bytes) -> dict:
    """Check the file and keep only the three fields the alert needs."""
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise OwnerLookupError(f"owner file for {lead_id} is not valid JSON") from error

    if not isinstance(data, dict):
        raise OwnerLookupError(f"owner file for {lead_id} is not a JSON object")
    if data.get("lead_id", lead_id) != lead_id:
        raise OwnerLookupError(f"owner file for {lead_id} belongs to {data['lead_id']}")

    # A missing field becomes None; the processor decides what to show for it.
    return {field: data.get(field) for field in _OWNER_FIELDS}
