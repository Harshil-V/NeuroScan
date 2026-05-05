from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.clients.orthanc import OrthancClient, OrthancError
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

    write_event(
        session,
        event_type="dicom_uploaded",
        status="success",
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
