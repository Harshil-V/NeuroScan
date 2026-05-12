"""The FastAPI BackgroundTask body for reconstruction jobs.

This is a sync function on purpose: FastAPI BackgroundTasks runs sync
callables in its threadpool, which is the right execution model for
CPU-bound FFT work. If declared `async def`, it would block the event loop.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.clients.orthanc import OrthancError
from app.clients.s3 import S3Client
from app.config import Settings
from app.db import get_engine
from app.models.reconstruction import ReconstructionJob
from app.services.reconstruction.dicom_writer import image_to_mr_dicom
from app.services.reconstruction.fft_reconstruct import reconstruct
from app.services.reconstruction.kspace_loader import (
    InvalidKspaceError,
    UnsupportedShapeError,
    load,
)
from app.services.reconstruction.metrics import psnr, ssim
from app.services.storage import tee_to_s3


def _now() -> datetime:
    return datetime.now(UTC)


def _set_status(
    session: Session,
    job_id: uuid.UUID,
    **fields,
) -> None:
    session.execute(
        update(ReconstructionJob).where(ReconstructionJob.job_id == job_id).values(**fields)
    )
    session.commit()


def run_job(job_id: uuid.UUID, tempfile_path: Path, settings: Settings) -> None:
    """Run reconstruction for one job. Updates the DB row in place.

    Always sets a terminal status. Always deletes the tempfile.
    """
    engine = get_engine()
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    started = time.monotonic()

    try:
        with session_factory() as session:
            _set_status(
                session,
                job_id,
                status="running",
                started_at=_now(),
            )

        kspace, ground_truth = load(tempfile_path)
        recon_image = reconstruct(kspace)

        psnr_value = ssim_value = None
        if ground_truth is not None:
            psnr_value = psnr(recon_image, ground_truth)
            ssim_value = ssim(recon_image, ground_truth)

        write_result = image_to_mr_dicom(
            recon_image,
            source_name=tempfile_path.name,
        )

        # Use a sync httpx call to upload to Orthanc.
        # OrthancClient (in app/clients/orthanc.py) is async — fine for FastAPI
        # request handlers, but in this sync BackgroundTask body we want a sync
        # call that runs in the threadpool without spinning up an event loop.
        orthanc_instance_id = _upload_sync(settings, write_result.dicom_bytes)

        # Tee reconstructed DICOM to MinIO (best-effort).
        recon_sha256 = hashlib.sha256(write_result.dicom_bytes).hexdigest()
        try:
            s3 = S3Client(
                endpoint_url=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                bucket=settings.minio_bucket,
                region=settings.minio_region,
            )
            with session_factory() as session:
                tee_to_s3(
                    s3=s3,
                    session=session,
                    body=write_result.dicom_bytes,
                    sha256=recon_sha256,
                    source="reconstruction_output",
                )
        except Exception as exc:  # noqa: BLE001
            # Best-effort: log and continue. Job stays 'completed'.
            logging.getLogger(__name__).warning("Recon S3 tee failed for job %s: %s", job_id, exc)

        duration_ms = int((time.monotonic() - started) * 1000)

        with session_factory() as session:
            _set_status(
                session,
                job_id,
                status="completed",
                completed_at=_now(),
                output_dicom_uid=write_result.study_instance_uid,
                output_orthanc_instance_id=orthanc_instance_id,
                psnr_db=psnr_value,
                ssim=ssim_value,
                duration_ms=duration_ms,
                input_shape=str(kspace.shape),
            )

    except (InvalidKspaceError, UnsupportedShapeError) as exc:
        with session_factory() as session:
            _set_status(
                session,
                job_id,
                status="failed",
                completed_at=_now(),
                error_message=f"invalid_kspace: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
    except OrthancError as exc:
        with session_factory() as session:
            _set_status(
                session,
                job_id,
                status="failed",
                completed_at=_now(),
                error_message=f"orthanc_rejected: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
    except Exception as exc:  # noqa: BLE001 — defensive
        with session_factory() as session:
            _set_status(
                session,
                job_id,
                status="failed",
                completed_at=_now(),
                error_message=f"reconstruction_failed: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
    finally:
        with contextlib.suppress(OSError):
            tempfile_path.unlink(missing_ok=True)


def _upload_sync(settings: Settings, dicom_bytes: bytes) -> str:
    """Sync-only Orthanc instance upload (parallel to the async OrthancClient).

    The async client is fine for FastAPI request handlers, but here we want a
    plain sync call that runs in the BackgroundTask threadpool.
    """
    url = f"{settings.orthanc_url.rstrip('/')}/instances"
    auth = (settings.orthanc_user, settings.orthanc_password)
    with httpx.Client(timeout=30.0, auth=auth) as client:
        response = client.post(
            url,
            content=dicom_bytes,
            headers={"Content-Type": "application/dicom"},
        )
    if response.status_code >= 400:
        raise OrthancError(f"Orthanc rejected upload: {response.status_code} {response.text}")
    body = response.json()
    instance_id = body.get("ID")
    if not instance_id:
        raise OrthancError(f"Orthanc upload missing ID in response: {body}")
    return instance_id
