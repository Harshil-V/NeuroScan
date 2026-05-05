from fastapi import FastAPI

from app.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="NeuroScan API", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
