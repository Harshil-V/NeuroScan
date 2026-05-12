from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import audit, dicom, health, reconstruction, storage, studies
from app.services.upload import UploadFailedError


def create_app() -> FastAPI:
    app = FastAPI(title="NeuroScan API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(UploadFailedError)
    async def upload_failed_handler(_: Request, exc: UploadFailedError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.on_event("startup")
    async def _ensure_bucket_on_startup() -> None:
        import logging

        from app.clients.s3 import S3Client, S3Error
        from app.config import get_settings

        settings = get_settings()
        try:
            client = S3Client(
                endpoint_url=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                bucket=settings.minio_bucket,
                region=settings.minio_region,
            )
            client.ensure_bucket()
        except S3Error as exc:
            logging.getLogger(__name__).warning(
                "MinIO bucket setup failed (will retry on first use): %s", exc
            )

    app.include_router(health.router)
    app.include_router(dicom.router)
    app.include_router(dicom.instances_router)
    app.include_router(studies.router)
    app.include_router(audit.router)
    app.include_router(reconstruction.router)
    app.include_router(storage.router)
    return app


app = create_app()
