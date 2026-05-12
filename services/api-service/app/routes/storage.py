"""Storage object endpoints: list, detail, presigned URL."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.s3 import S3Client
from app.config import Settings, get_settings
from app.db import get_session
from app.models.storage import StorageObject
from app.schemas.storage import (
    PresignedUrlOut,
    StorageObjectList,
    StorageObjectOut,
)
from app.services.storage import StorageObjectNotFoundError, mint_presigned_url

router = APIRouter(prefix="/api/storage", tags=["storage"])


def get_s3_client(settings: Settings = Depends(get_settings)) -> S3Client:
    return S3Client(
        endpoint_url=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        region=settings.minio_region,
    )


@router.get("/objects", response_model=StorageObjectList)
async def list_objects(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source: Literal["dicom_upload", "reconstruction_output"] | None = None,
    sha256: str | None = None,
    session: Session = Depends(get_session),
) -> StorageObjectList:
    stmt = select(StorageObject)
    count_stmt = select(func.count()).select_from(StorageObject)
    if source:
        stmt = stmt.where(StorageObject.source == source)
        count_stmt = count_stmt.where(StorageObject.source == source)
    if sha256:
        stmt = stmt.where(StorageObject.sha256 == sha256)
        count_stmt = count_stmt.where(StorageObject.sha256 == sha256)
    stmt = stmt.order_by(StorageObject.created_at.desc()).limit(limit).offset(offset)
    items = list(session.scalars(stmt))
    total = session.scalar(count_stmt) or 0
    return StorageObjectList(
        items=[StorageObjectOut.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/objects/{object_id}", response_model=StorageObjectOut)
async def get_object(
    object_id: int,
    session: Session = Depends(get_session),
) -> StorageObjectOut:
    obj = session.get(StorageObject, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="storage_object_not_found")
    return StorageObjectOut.model_validate(obj)


@router.get("/objects/{object_id}/presigned-url", response_model=PresignedUrlOut)
async def get_presigned_url(
    object_id: int,
    expires: int = Query(300, ge=60, le=3600),
    session: Session = Depends(get_session),
    s3: S3Client = Depends(get_s3_client),
) -> PresignedUrlOut:
    try:
        url, expires_at = mint_presigned_url(
            s3=s3, session=session, object_id=object_id, expires_in=expires
        )
    except StorageObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PresignedUrlOut(url=url, expires_at=expires_at)
