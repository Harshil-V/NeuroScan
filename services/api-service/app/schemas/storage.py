from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StorageObjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bucket: str
    object_key: str
    sha256: str
    content_type: str
    size_bytes: int
    source: Literal["dicom_upload", "reconstruction_output"]
    created_at: datetime


class StorageObjectList(BaseModel):
    items: list[StorageObjectOut]
    total: int
    limit: int
    offset: int


class PresignedUrlOut(BaseModel):
    url: str
    expires_at: datetime
