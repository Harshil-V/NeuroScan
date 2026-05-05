from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.clients.orthanc import OrthancClient, OrthancError
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

    body = {
        "status": "ok" if (orthanc_ok and db_ok) else "degraded",
        "service": "api-service",
        "version": __version__,
        "orthanc_reachable": orthanc_ok,
        "db_reachable": db_ok,
    }
    code = 200 if (orthanc_ok and db_ok) else 503
    return JSONResponse(body, status_code=code)
