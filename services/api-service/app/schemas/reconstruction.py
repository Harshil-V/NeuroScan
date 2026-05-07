import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReconstructionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    input_file_name: str
    input_format: Literal["npy", "npz", "h5"]
    input_shape: str | None
    output_dicom_uid: str | None
    output_orthanc_instance_id: str | None
    psnr_db: float | None
    ssim: float | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ReconstructionJobCreated(BaseModel):
    job_id: uuid.UUID
    status: Literal["queued"]
    input_file_name: str
    input_format: Literal["npy", "npz", "h5"]
    created_at: datetime


class ReconstructionJobList(BaseModel):
    items: list[ReconstructionJobOut]
    total: int
    limit: int
    offset: int
