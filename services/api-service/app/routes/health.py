from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.clients.orthanc import OrthancClient, OrthancError
from app.clients.s3 import S3Client
from app.config import get_settings
from app.db import get_engine

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    settings = get_settings()
    orthanc_ok = False
    try:
        client = OrthancClient(
            base_url=settings.orthanc_url,
            user=settings.orthanc_user,
            password=settings.orthanc_password,
            max_retries=1,
        )
        await client.system()
        orthanc_ok = True
    except OrthancError:
        orthanc_ok = False

    db_ok = False
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    minio_ok = False
    try:
        s3 = S3Client(
            endpoint_url=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            region=settings.minio_region,
        )
        minio_ok = s3.is_reachable()
    except Exception:
        minio_ok = False

    if not (orthanc_ok and db_ok):
        status = "degraded"
        code = 503
    elif not minio_ok:
        # Orthanc + DB up, MinIO down → degraded but still 200 (best-effort sidecar)
        status = "degraded"
        code = 200
    else:
        status = "ok"
        code = 200

    return JSONResponse(
        {
            "status": status,
            "service": "api-service",
            "version": __version__,
            "orthanc_reachable": orthanc_ok,
            "db_reachable": db_ok,
            "minio_reachable": minio_ok,
        },
        status_code=code,
    )
