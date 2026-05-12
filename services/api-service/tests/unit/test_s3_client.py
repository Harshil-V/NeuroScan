from datetime import UTC

import boto3
import pytest
from moto import mock_aws

from app.clients.s3 import S3Client, S3Error


@pytest.fixture
def s3_client():
    """A real S3Client wired against moto's in-memory AWS mock."""
    with mock_aws():
        # moto needs a region but doesn't actually validate creds
        client = S3Client(
            endpoint_url=None,  # let boto3 pick the moto-mocked AWS endpoint
            access_key="testing",
            secret_key="testing",
            bucket="test-bucket",
            region="us-east-1",
        )
        yield client


def test_ensure_bucket_creates_when_absent(s3_client):
    s3_client.ensure_bucket()
    # Verify via raw boto3
    raw = boto3.client("s3", region_name="us-east-1")
    buckets = [b["Name"] for b in raw.list_buckets()["Buckets"]]
    assert "test-bucket" in buckets


def test_ensure_bucket_is_idempotent(s3_client):
    s3_client.ensure_bucket()
    s3_client.ensure_bucket()  # second call should not raise
    raw = boto3.client("s3", region_name="us-east-1")
    buckets = [b["Name"] for b in raw.list_buckets()["Buckets"]]
    assert buckets.count("test-bucket") == 1


def test_put_object_writes_bytes(s3_client):
    s3_client.ensure_bucket()
    s3_client.put_object(
        key="dicom/abc123.dcm",
        body=b"fake-dicom-bytes",
        content_type="application/dicom",
    )
    head = s3_client.head_object("dicom/abc123.dcm")
    assert head["ContentType"] == "application/dicom"
    assert head["ContentLength"] == len(b"fake-dicom-bytes")


def test_is_reachable_returns_true_when_bucket_exists(s3_client):
    s3_client.ensure_bucket()
    assert s3_client.is_reachable() is True


def test_generate_presigned_get_url_returns_signed_url(s3_client):
    s3_client.ensure_bucket()
    s3_client.put_object(key="dicom/x.dcm", body=b"data")
    url, expires_at = s3_client.generate_presigned_get_url("dicom/x.dcm", expires_in=300)
    assert "X-Amz-Signature" in url
    assert "X-Amz-Expires=300" in url
    # expires_at should be ~5 minutes in the future
    from datetime import datetime

    delta = (expires_at - datetime.now(UTC)).total_seconds()
    assert 290 <= delta <= 310


def test_put_object_raises_s3error_on_missing_bucket(s3_client):
    # Don't ensure_bucket; put should fail
    with pytest.raises(S3Error):
        s3_client.put_object(key="x", body=b"data")
