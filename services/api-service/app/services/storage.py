"""Tee uploads to S3 and look up storage objects.

Best-effort: tee_to_s3 returns None on S3 failure so the caller can record
a 'success_minio_skipped' audit row instead of failing the whole request.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.s3 import S3Client, S3Error
from app.models.storage import StorageObject

logger = logging.getLogger(__name__)

KEY_PREFIX_DICOM = "dicom/"
KEY_PREFIX_RECONSTRUCTION = "reconstructed/"

StorageSource = Literal["dicom_upload", "reconstruction_output"]


class StorageObjectNotFoundError(Exception):
    """Raised when a storage_object id does not exist."""


def object_key_for(*, source: StorageSource, sha256: str) -> str:
    if source == "dicom_upload":
        return f"{KEY_PREFIX_DICOM}{sha256}.dcm"
    if source == "reconstruction_output":
        return f"{KEY_PREFIX_RECONSTRUCTION}{sha256}.dcm"
    raise ValueError(f"Unknown source: {source}")


def tee_to_s3(
    *,
    s3: S3Client,
    session: Session,
    body: bytes,
    sha256: str,
    source: StorageSource,
    content_type: str = "application/dicom",
) -> StorageObject | None:
    """Write bytes to S3 and record a storage_objects row.

    Returns the row on success, None on S3 failure (best-effort).
    Idempotent: if a row already exists for (bucket, object_key), reuse it.
    """
    key = object_key_for(source=source, sha256=sha256)

    try:
        s3.put_object(key=key, body=body, content_type=content_type)
    except S3Error as exc:
        logger.warning("S3 tee failed for %s: %s", key, exc)
        return None

    existing = session.scalar(
        select(StorageObject).where(
            StorageObject.bucket == s3.bucket,
            StorageObject.object_key == key,
        )
    )
    if existing is not None:
        return existing

    obj = StorageObject(
        bucket=s3.bucket,
        object_key=key,
        sha256=sha256,
        content_type=content_type,
        size_bytes=len(body),
        source=source,
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def mint_presigned_url(
    *,
    s3: S3Client,
    session: Session,
    object_id: int,
    expires_in: int,
    public_base_url: str = "",
) -> tuple[str, datetime]:
    obj = session.get(StorageObject, object_id)
    if obj is None:
        raise StorageObjectNotFoundError(f"storage_object {object_id} not found")
    return s3.generate_presigned_get_url(
        obj.object_key, expires_in=expires_in, public_base_url=public_base_url
    )
