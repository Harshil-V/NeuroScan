"""Sync S3 client backed by boto3, configured for MinIO endpoint by default.

Migrating to AWS S3 (Slice 10+) requires only setting endpoint_url=None and
swapping the credentials to AWS-issued ones. All other code stays the same.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class S3Error(Exception):
    """Raised when an S3 operation fails."""


class S3Client:
    def __init__(
        self,
        *,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url or ""
        self._access_key = access_key
        self._secret_key = secret_key
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3},
                s3={"addressing_style": "path"},
            ),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchBucket"):
                try:
                    self._client.create_bucket(Bucket=self._bucket)
                except (BotoCoreError, ClientError) as create_exc:
                    raise S3Error(f"create_bucket failed: {create_exc}") from create_exc
                return
            raise S3Error(f"head_bucket failed: {exc}") from exc

    def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str = "application/dicom",
    ) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(f"put_object {key} failed: {exc}") from exc

    def head_object(self, key: str) -> dict:
        try:
            return self._client.head_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(f"head_object {key} failed: {exc}") from exc

    def is_reachable(self) -> bool:
        try:
            self._client.list_buckets()
            return True
        except (BotoCoreError, ClientError) as exc:
            logger.warning("S3 reachability check failed: %s", exc)
            return False

    def generate_presigned_get_url(
        self, key: str, *, expires_in: int = 300, public_base_url: str = ""
    ) -> tuple[str, datetime]:
        """Return a presigned GET URL and its expiry.

        When running inside Docker, ``endpoint_url`` is the internal hostname
        (e.g. ``http://minio:9000``).  Presigned URLs include the endpoint
        hostname in the signature (``X-Amz-SignedHeaders: host``), so the URL
        must be signed with the same hostname the browser will use to fetch it.

        Pass ``public_base_url`` (e.g. ``http://localhost:9000``) to sign the
        URL against the browser-reachable origin instead of the internal one.
        A temporary boto3 client pointed at ``public_base_url`` is used only
        for signing; no network call is made.
        """
        signing_client = self._client
        if public_base_url and public_base_url != self._endpoint_url:
            signing_client = boto3.client(
                "s3",
                endpoint_url=public_base_url,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                ),
            )
        try:
            url = signing_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(f"presign {key} failed: {exc}") from exc
        return url, datetime.now(UTC) + timedelta(seconds=expires_in)
