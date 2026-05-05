from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import dicom, health, studies
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

    app.include_router(health.router)
    app.include_router(dicom.router)
    app.include_router(dicom.instances_router)
    app.include_router(studies.router)
    return app


app = create_app()
