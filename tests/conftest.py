"""Shared test fixtures. pytest loads this file automatically."""

import boto3
import pytest
from moto import mock_aws

BUCKET = "leadrelay-test"


@pytest.fixture(autouse=True)
def fake_aws_credentials(monkeypatch):
    """Fake keys, so no test can ever reach your real AWS account."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def s3():
    """An S3 client talking to moto's in-memory fake S3, with our bucket created."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client
