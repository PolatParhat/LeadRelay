"""Format the "New Lead Alert" and post it to Slack through an incoming webhook.

A Slack incoming webhook is a secret URL: anyone who POSTs JSON like
{"text": "hello"} to it makes a message appear in one channel. So the URL is
a secret (kept in SSM Parameter Store) and is never written to logs or errors.

Slack's answers:
    200            delivered
    429            too many messages (about 1 per second allowed): wait, retry
    5xx / no reply Slack trouble: wait, retry
    other 4xx      the URL is wrong or revoked: retrying will not help
"""

import json
import logging
import time
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 5
ATTEMPTS = 3
MAX_WAIT_SECONDS = 5  # keep total time well inside the processor's 30 s limit

UNASSIGNED = "UNASSIGNED"
NOT_AVAILABLE = "N/A"

log = logging.getLogger(__name__)


class AlertError(Exception):
    """Slack did not accept the alert. The caller releases the marker and raises."""


def _escape(value) -> str:
    """Slack treats & < > as control characters; escape them so a lead named
    "<!channel>" cannot ping the whole channel."""
    text = NOT_AVAILABLE if value in (None, "") else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(record: dict) -> str:
    """The alert text, in the field order the requirements list."""
    owner = record.get("lead_owner") if record.get("owner_found") else None
    lines = [
        ":rotating_light: *New Lead Alert*",
        f"*Name:* {_escape(record.get('display_name'))}",
        f"*Lead ID:* {_escape(record.get('lead_id'))}",
        f"*Created Date:* {_escape(record.get('date_created'))}",
        f"*Label:* {_escape(record.get('status_label'))}",
        f"*Email:* {_escape(record.get('lead_email'))}",
        f"*Lead Owner:* {_escape(owner) if owner else UNASSIGNED}",
        f"*Funnel:* {_escape(record.get('funnel'))}",
    ]
    return "\n".join(lines)


def send_alert(webhook_url: str, record: dict, timeout: float = TIMEOUT_SECONDS,
               attempts: int = ATTEMPTS, sleep=time.sleep) -> None:
    """POST the alert to Slack. Returns when Slack says 200; raises AlertError otherwise."""
    lead_id = record.get("lead_id")
    payload = json.dumps({"text": format_message(record)}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url, data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )

    for attempt in range(1, attempts + 1):
        wait = 2 ** (attempt - 1)  # 1 s, 2 s, ... (exponential backoff)
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                pass
            log.info("alert sent", extra={"lead_id": lead_id})
            return

        except urllib.error.HTTPError as error:
            if error.code == 429:
                # Slack says how long to wait in the Retry-After header.
                wait = _retry_after(error.headers.get("Retry-After"), default=wait)
                problem = "HTTP 429 rate limited"
            elif error.code >= 500:
                problem = f"HTTP {error.code}"
            else:
                # Never put the URL in the message: it is the secret.
                raise AlertError(f"Slack refused the alert for {lead_id}: HTTP {error.code} "
                                 "(check the webhook URL in SSM)") from None

        except (urllib.error.URLError, TimeoutError) as error:
            problem = f"network error: {type(error).__name__}"

        if attempt < attempts:
            log.warning("alert failed, retrying",
                        extra={"lead_id": lead_id, "problem": problem, "wait_s": wait})
            sleep(wait)

    raise AlertError(f"Slack alert for {lead_id} failed after {attempts} attempts: {problem}")


def _retry_after(header, default: float) -> float:
    try:
        return min(float(header), MAX_WAIT_SECONDS)
    except (TypeError, ValueError):
        return default
