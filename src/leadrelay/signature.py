"""Check that a webhook really came from Close.

Close signs every webhook it sends. It takes the timestamp header plus the raw
body, and computes HMAC-SHA256 with the subscription's secret signature_key
(given to us as a hex string). It sends the result in the Close-Sig-Hash header.
We do the same calculation; if our result matches theirs, the request is genuine
and was not changed on the way.
"""

import hashlib
import hmac
import time

MAX_AGE_SECONDS = 300  # reject signatures older than 5 minutes (stops replays)


def compute_signature(signature_key_hex: str, timestamp: str, raw_body: str) -> str:
    """Return the hex HMAC-SHA256 of timestamp + raw_body, keyed with the hex key."""
    key = bytes.fromhex(signature_key_hex)
    message = (timestamp + raw_body).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def is_valid_signature(
    signature_key_hex: str,
    timestamp: str | None,
    sig_hash: str | None,
    raw_body: str,
    now: float | None = None,
    max_age_seconds: int = MAX_AGE_SECONDS,
) -> bool:
    """True only if the headers are present, fresh, and the hash matches.

    `now` can be passed in by tests; normally it is the current time.
    """
    if not timestamp or not sig_hash:
        return False

    try:
        sent_at = int(timestamp)
    except ValueError:
        return False

    if now is None:
        now = time.time()
    if abs(now - sent_at) > max_age_seconds:
        return False

    expected = compute_signature(signature_key_hex, timestamp, raw_body)
    # compare_digest takes the same time whether the first or last character
    # differs, so an attacker cannot guess the hash one character at a time.
    return hmac.compare_digest(expected.encode("utf-8"), sig_hash.encode("utf-8"))
