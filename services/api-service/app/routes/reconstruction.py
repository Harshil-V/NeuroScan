"""Reconstruction job endpoints: POST to submit, GET to inspect."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.models.reconstruction import ReconstructionJob
from app.schemas.reconstruction import (
    ReconstructionJobCreated,
    ReconstructionJobList,
    ReconstructionJobOut,
)
from app.services.reconstruction.job_runner import run_job
from app.services.reconstruction.kspace_loader import (
    InvalidKspaceError,
    UnsupportedShapeError,
    load,
)

router = APIRouter(prefix="/api/reconstruction", tags=["reconstruction"])

ALLOWED_EXTENSIONS = {".npy", ".npz", ".h5", ".hdf5"}
MAX_BYTES = 100 * 1024 * 1024  # 100 MB
TEMPDIR_PREFIX = "neuroscan-recon-"


def _ext_to_format(ext: str) -> str:
    if ext == ".npy":
        return "npy"
    if ext == ".npz":
        return "npz"
    return "h5"  # .h5 or .hdf5


@router.post(
    "/jobs",
    response_model=ReconstructionJobCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ReconstructionJobCreated:
    filename = file.filename or "upload.bin"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"unsupported file extension: {ext}",
                "code": "invalid_kspace",
            },
        )

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "detail": f"file too large: {len(data)} bytes (max {MAX_BYTES})",
                "code": "file_too_large",
            },
        )

    # Save to a tempfile so the BackgroundTask can read it after the response
    tmpdir = Path(tempfile.mkdtemp(prefix=TEMPDIR_PREFIX))
    tempfile_path = tmpdir / filename
    tempfile_path.write_bytes(data)

    # Pre-validate so we can return 400 before queueing
    try:
        load(tempfile_path)
    except InvalidKspaceError as exc:
        tempfile_path.unlink(missing_ok=True)
        tmpdir.rmdir()
        raise HTTPException(
            status_code=400,
            detail={"detail": str(exc), "code": "invalid_kspace"},
        ) from exc
    except UnsupportedShapeError as exc:
        tempfile_path.unlink(missing_ok=True)
        tmpdir.rmdir()
        raise HTTPException(
            status_code=400,
            detail={"detail": str(exc), "code": "unsupported_shape"},
        ) from exc

    job = ReconstructionJob(
        job_id=uuid.uuid4(),
        status="queued",
        input_file_name=filename,
        input_format=_ext_to_format(ext),
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    background_tasks.add_task(run_job, job.job_id, tempfile_path, settings)

    return ReconstructionJobCreated(
        job_id=job.job_id,
        status="queued",
        input_file_name=job.input_file_name,
        input_format=job.input_format,  # type: ignore[arg-type]
        created_at=job.created_at,
    )


@router.get("/jobs/{job_id}", response_model=ReconstructionJobOut)
async def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ReconstructionJobOut:
    job = session.scalar(select(ReconstructionJob).where(ReconstructionJob.job_id == job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return ReconstructionJobOut.model_validate(job)


@router.get("/jobs", response_model=ReconstructionJobList)
async def list_jobs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    session: Session = Depends(get_session),
) -> ReconstructionJobList:
    stmt = select(ReconstructionJob)
    count_stmt = select(func.count()).select_from(ReconstructionJob)
    if status_filter:
        stmt = stmt.where(ReconstructionJob.status == status_filter)
        count_stmt = count_stmt.where(ReconstructionJob.status == status_filter)
    stmt = stmt.order_by(ReconstructionJob.created_at.desc()).limit(limit).offset(offset)
    items = list(session.scalars(stmt))
    total = session.scalar(count_stmt) or 0
    return ReconstructionJobList(
        items=[ReconstructionJobOut.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )
