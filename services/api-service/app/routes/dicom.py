from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.clients.orthanc import OrthancClient, OrthancError
from app.clients.s3 import S3Client
from app.config import Settings, get_settings
from app.db import get_session
from app.routes.storage import get_s3_client
from app.schemas.upload import UploadResult
from app.services.upload import handle_upload

router = APIRouter(prefix="/api/dicom", tags=["dicom"])


def get_orthanc_client(settings: Settings = Depends(get_settings)) -> OrthancClient:
    return OrthancClient(
        base_url=settings.orthanc_url,
        user=settings.orthanc_user,
        password=settings.orthanc_password,
    )


@router.post(
    "/upload",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dicom(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    orthanc: OrthancClient = Depends(get_orthanc_client),
    s3: S3Client = Depends(get_s3_client),
    settings: Settings = Depends(get_settings),
) -> UploadResult:
    data = await file.read()
    result = await handle_upload(
        session=session,
        orthanc=orthanc,
        dicom_bytes=data,
        s3=s3,
        deid_salt=settings.deid_hash_salt,
    )
    return UploadResult(
        status="uploaded",
        study_instance_uid=result.study_instance_uid,
        series_instance_uid=result.series_instance_uid,
        sop_instance_uid=result.sop_instance_uid,
        orthanc_instance_id=result.orthanc_instance_id,
        checksum_sha256=result.checksum_sha256,
        phi_findings=result.phi_findings,
    )


instances_router = APIRouter(prefix="/api/instances", tags=["instances"])


@instances_router.get("/{orthanc_instance_id}/preview.png")
async def preview_png(
    orthanc_instance_id: str,
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> Response:
    try:
        content, content_type = await orthanc.get_instance_preview(orthanc_instance_id)
    except OrthancError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type=content_type)
