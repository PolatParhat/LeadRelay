"""Tests for leadrelay.config (SSM faked by moto, no real AWS)."""

import boto3
import pytest
from moto import mock_aws

from leadrelay.config import ConfigError, SecretStore, load_settings


# ---------- settings ----------

def test_defaults_when_only_bucket_is_set():
    settings = load_settings({"BUCKET_NAME": "leadrelay-123"})
    assert settings.bucket_name == "leadrelay-123"
    assert settings.owner_max_tries == 6
    assert settings.marker_stale_seconds == 120
    assert settings.owner_base_url == "https://dea-lead-owner.s3.us-east-1.amazonaws.com"
    assert settings.signature_key_param == "/leadrelay/close_signature_key"
    assert settings.slack_webhook_param == "/leadrelay/slack_webhook_url"


def test_values_from_environment_override_defaults():
    settings = load_settings({
        "BUCKET_NAME": "b-1", "OWNER_MAX_TRIES": "3", "OWNER_BASE_URL": "http://127.0.0.1:8000/",
    })
    assert settings.owner_max_tries == 3
    assert settings.owner_base_url == "http://127.0.0.1:8000"  # trailing / removed


@pytest.mark.parametrize("env", [{}, {"BUCKET_NAME": "  "}])
def test_missing_bucket_name_raises(env):
    with pytest.raises(ConfigError, match="BUCKET_NAME"):
        load_settings(env)


@pytest.mark.parametrize("value, problem", [("six", "whole number"), ("0", "at least 1")])
def test_bad_owner_max_tries_raises(value, problem):
    with pytest.raises(ConfigError, match=problem):
        load_settings({"BUCKET_NAME": "b-1", "OWNER_MAX_TRIES": value})


def test_settings_cannot_be_changed_later():
    settings = load_settings({"BUCKET_NAME": "b-1"})
    with pytest.raises(AttributeError):
        settings.bucket_name = "other"


# ---------- secrets ----------

@pytest.fixture
def ssm():
    with mock_aws():
        yield boto3.client("ssm", region_name="us-east-1")


def test_secret_is_read_and_decrypted(ssm):
    ssm.put_parameter(Name="/leadrelay/slack_webhook_url", Value="https://hooks.example/x", Type="SecureString")
    assert SecretStore(ssm).get("/leadrelay/slack_webhook_url") == "https://hooks.example/x"


def test_secret_is_fetched_only_once(ssm):
    ssm.put_parameter(Name="/leadrelay/k", Value="first", Type="SecureString")
    store = SecretStore(ssm)
    assert store.get("/leadrelay/k") == "first"
    ssm.put_parameter(Name="/leadrelay/k", Value="second", Type="SecureString", Overwrite=True)
    assert store.get("/leadrelay/k") == "first"  # cached for this container's life


def test_missing_secret_raises_config_error(ssm):
    with pytest.raises(ConfigError, match="does not exist"):
        SecretStore(ssm).get("/leadrelay/nope")


def test_placeholder_secret_raises_config_error(ssm):
    ssm.put_parameter(Name="/leadrelay/k", Value="CHANGE_ME", Type="SecureString")
    with pytest.raises(ConfigError, match="placeholder"):
        SecretStore(ssm).get("/leadrelay/k")
