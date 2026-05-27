"""Integration-test-scoped fixtures.

Adds an autouse cleanup so every integration test starts with empty tables,
regardless of whether it requests ``db_session``.
The session-scoped ``configure_settings`` fixture creates the schema once;
the per-test ``api_client`` fixture clears Orthanc state. This fixture
covers the database side for tests that don't take ``db_session``.

Renamed from ``_truncate_audit_events`` to ``_truncate_tables_between_tests``
to reflect that it now covers all mutable tables (audit_events,
reconstruction_jobs, storage_objects) and the MinIO test bucket.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine


@pytest.fixture(autouse=True)
def _truncate_tables_between_tests(database_url: str) -> Iterator[None]:
    yield
    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "TRUNCATE TABLE audit_events, reconstruction_jobs, storage_objects RESTART IDENTITY"
            )
    finally:
        engine.dispose()

    # Empty the test bucket between tests
    import boto3
    from botocore.client import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
        region_name=os.environ.get("MINIO_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    bucket = os.environ["MINIO_BUCKET"]
    try:
        contents = s3.list_objects_v2(Bucket=bucket).get("Contents") or []
        for obj in contents:
            s3.delete_object(Bucket=bucket, Key=obj["Key"])
    except Exception:  # noqa: BLE001
        pass
