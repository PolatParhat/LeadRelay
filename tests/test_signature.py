"""Tests for leadrelay.signature (no AWS, no network)."""

from leadrelay.signature import compute_signature, is_valid_signature

KEY = "a1b2c3d4" * 8  # fake 32-byte key written as 64 hex characters
NOW = 1_762_860_000  # a fixed "current time" so the tests never depend on the clock
TS = str(NOW)
BODY = '{"event": {"object_type": "lead", "action": "created", "lead_id": "lead_123"}}'


def signed_hash(body=BODY, ts=TS, key=KEY):
    """What Close would put in the Close-Sig-Hash header."""
    return compute_signature(key, ts, body)


def test_valid_signature_is_accepted():
    assert is_valid_signature(KEY, TS, signed_hash(), BODY, now=NOW)


def test_changed_body_is_rejected():
    tampered = BODY.replace("lead_123", "lead_999")
    assert not is_valid_signature(KEY, TS, signed_hash(), tampered, now=NOW)


def test_wrong_key_is_rejected():
    other_key = "ff" * 32
    assert not is_valid_signature(KEY, TS, signed_hash(key=other_key), BODY, now=NOW)


def test_old_timestamp_is_rejected():
    six_minutes_later = NOW + 360
    assert not is_valid_signature(KEY, TS, signed_hash(), BODY, now=six_minutes_later)


def test_timestamp_within_five_minutes_is_accepted():
    four_minutes_later = NOW + 240
    assert is_valid_signature(KEY, TS, signed_hash(), BODY, now=four_minutes_later)


def test_missing_headers_are_rejected():
    assert not is_valid_signature(KEY, None, signed_hash(), BODY, now=NOW)
    assert not is_valid_signature(KEY, TS, None, BODY, now=NOW)
    assert not is_valid_signature(KEY, "", "", BODY, now=NOW)


def test_non_numeric_timestamp_is_rejected():
    assert not is_valid_signature(KEY, "yesterday", signed_hash(ts="yesterday"), BODY, now=NOW)


def test_garbage_hash_is_rejected_without_crashing():
    assert not is_valid_signature(KEY, TS, "not-a-hash-é", BODY, now=NOW)


def test_matches_independent_calculation():
    """Same result as a by-hand HMAC, so we follow Close's recipe exactly."""
    import hashlib
    import hmac

    by_hand = hmac.new(bytes.fromhex(KEY), (TS + BODY).encode(), hashlib.sha256).hexdigest()
    assert compute_signature(KEY, TS, BODY) == by_hand
