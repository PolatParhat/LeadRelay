"""Settings and secrets, in one place.

Settings (not secret) come from environment variables that Terraform sets on
each Lambda. Secrets come from SSM Parameter Store, so they never appear in
code, git, Terraform files or the Lambda console.

    Environment variable          Default                         Meaning
    BUCKET_NAME                   (required)                      leadrelay-{account_id}
    OWNER_MAX_TRIES               6                               try that alerts UNASSIGNED
    MARKER_STALE_SECONDS          120                             "sending" marker older = crashed
    OWNER_BASE_URL                https://dea-lead-owner...       lookup bucket URL
    SIGNATURE_KEY_PARAM           /leadrelay/close_signature_key  SSM name of the Close key
    SLACK_WEBHOOK_PARAM           /leadrelay/slack_webhook_url    SSM name of the Slack URL
"""

import os
import time
from dataclasses import dataclass

from leadrelay.lookup import OWNER_BASE_URL

# Terraform creates each SSM parameter with this value; the user replaces it.
PLACEHOLDER = "CHANGE_ME"


class ConfigError(Exception):
    """A setting or secret is missing or wrong. Fix the configuration, not the code."""


@dataclass(frozen=True)  # frozen: settings cannot be changed by accident later
class Settings:
    bucket_name: str
    owner_max_tries: int
    marker_stale_seconds: int
    owner_base_url: str
    signature_key_param: str
    slack_webhook_param: str


def load_settings(env=None) -> Settings:
    """Read settings from environment variables (or a dict, in tests)."""
    env = os.environ if env is None else env

    bucket = env.get("BUCKET_NAME", "").strip()
    if not bucket:
        raise ConfigError("BUCKET_NAME is not set")

    return Settings(
        bucket_name=bucket,
        owner_max_tries=_positive_int(env, "OWNER_MAX_TRIES", 6),
        marker_stale_seconds=_positive_int(env, "MARKER_STALE_SECONDS", 120),
        owner_base_url=env.get("OWNER_BASE_URL", OWNER_BASE_URL).rstrip("/"),
        signature_key_param=env.get("SIGNATURE_KEY_PARAM", "/leadrelay/close_signature_key"),
        slack_webhook_param=env.get("SLACK_WEBHOOK_PARAM", "/leadrelay/slack_webhook_url"),
    )


def _positive_int(env, name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None
    if value < 1:
        raise ConfigError(f"{name} must be at least 1, got {value}")
    return value


class SecretStore:
    """Reads secrets from SSM Parameter Store and remembers them.

    A Lambda container is reused for many invocations; create one SecretStore
    outside the handler and each secret is fetched only once per container
    ("cold start"), not once per lead.

    When a secret may have changed in SSM (for example the Close signature key
    was rotated), call refresh(name) to read it again. Refreshes of one name are
    limited to one per REFRESH_MIN_SECONDS, so a flood of bad requests cannot
    turn into a flood of SSM calls.
    """

    REFRESH_MIN_SECONDS = 60

    def __init__(self, ssm_client, clock=time.monotonic):
        self._ssm = ssm_client
        self._clock = clock
        self._cache = {}
        self._fetched_at = {}

    def get(self, name: str) -> str:
        if name not in self._cache:
            self._fetch(name)
        return self._cache[name]

    def refresh(self, name: str) -> bool:
        """Read `name` from SSM again. Returns True only if the value changed.

        Skipped (returns False) if this name was read less than
        REFRESH_MIN_SECONDS ago.
        """
        last = self._fetched_at.get(name)
        if last is not None and self._clock() - last < self.REFRESH_MIN_SECONDS:
            return False
        old = self._cache.get(name)
        self._fetch(name)
        return self._cache[name] != old

    def _fetch(self, name: str) -> None:
        try:
            response = self._ssm.get_parameter(Name=name, WithDecryption=True)
        except self._ssm.exceptions.ParameterNotFound:
            raise ConfigError(f"SSM parameter {name} does not exist") from None
        value = response["Parameter"]["Value"]
        if value == PLACEHOLDER:
            raise ConfigError(f"SSM parameter {name} still holds the placeholder; set the real value")
        self._cache[name] = value
        self._fetched_at[name] = self._clock()
