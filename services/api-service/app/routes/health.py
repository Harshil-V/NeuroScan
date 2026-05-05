from fastapi import APIRouter

from app import __version__

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "api-service",
        "version": __version__,
        "orthanc_reachable": None,
        "db_reachable": None,
    }
