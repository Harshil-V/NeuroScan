from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.clients.orthanc import OrthancClient, OrthancError
from app.clients.s3 import S3Client
from app.services.audit import write_event
from app.services.checksum import sha256_of
from app.services.dicom_validation import (
    InvalidDicomError,
    MissingRequiredTagError,
    validate_dicom,
)
from app.services.metadata import extract_metadata


@dataclass
class UploadResult:
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    orthanc_instance_id: str
    checksum_sha256: str


class UploadFailedError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def handle_upload(
    *,
    session: Session,
    orthanc: OrthancClient,
    dicom_bytes: bytes,
    s3: S3Client | None = None,
) -> UploadResult:
    checksum = sha256_of(dicom_bytes)
    try:
        ds = validate_dicom(dicom_bytes)
    except InvalidDicomError as exc:
        write_event(
            session,
            event_type="dicom_uploaded",
            status="failure",
            message=f"invalid_dicom: {exc}",
            checksum_sha256=checksum,
        )
        raise UploadFailedError("invalid_dicom", str(exc), 400) from exc
    except MissingRequiredTagError as exc:
        write_event(
            session,
            event_type="dicom_uploaded",
            status="failure",
            message=f"missing_required_tag: {exc.tag}",
            checksum_sha256=checksum,
        )
        raise UploadFailedError("missing_required_tag", str(exc), 400) from exc

    md = extract_metadata(ds)
    try:
        orthanc_instance_id = await orthanc.upload_instance(dicom_bytes)
    except OrthancError as exc:
        write_event(
            session,
            event_type="dicom_uploaded",
            status="failure",
            message=f"orthanc_rejected: {exc}",
            study_instance_uid=md["study_instance_uid"],
            series_instance_uid=md["series_instance_uid"],
            sop_instance_uid=md["sop_instance_uid"],
            checksum_sha256=checksum,
        )
        raise UploadFailedError("orthanc_rejected", str(exc), 502) from exc

    # Tee to S3 (best-effort)
    audit_status = "success"
    audit_message: str | None = None
    if s3 is not None:
        from app.services.storage import tee_to_s3

        storage_obj = tee_to_s3(
            s3=s3,
            session=session,
            body=dicom_bytes,
            sha256=checksum,
            source="dicom_upload",
        )
        if storage_obj is None:
            audit_status = "success_minio_skipped"
            audit_message = "MinIO tee failed (see logs); DICOM still in Orthanc"

    write_event(
        session,
        event_type="dicom_uploaded",
        status=audit_status,
        message=audit_message,
        study_instance_uid=md["study_instance_uid"],
        series_instance_uid=md["series_instance_uid"],
        sop_instance_uid=md["sop_instance_uid"],
        orthanc_instance_id=orthanc_instance_id,
        checksum_sha256=checksum,
    )

    return UploadResult(
        study_instance_uid=md["study_instance_uid"],
        series_instance_uid=md["series_instance_uid"],
        sop_instance_uid=md["sop_instance_uid"],
        orthanc_instance_id=orthanc_instance_id,
        checksum_sha256=checksum,
    )
