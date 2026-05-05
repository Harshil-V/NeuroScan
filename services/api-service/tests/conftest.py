"""Session-scoped fixtures: Postgres + Orthanc via testcontainers."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs
from testcontainers.postgres import PostgresContainer

import app.models  # noqa: F401  (registers models with Base.metadata)
from app.db import Base


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16", driver="psycopg") as pg:
        yield pg


@pytest.fixture(scope="session")
def orthanc_container() -> Iterator[DockerContainer]:
    container = (
        DockerContainer("orthancteam/orthanc:24.7.3")
        .with_exposed_ports(8042)
        .with_env("ORTHANC__REGISTERED_USERS", '{"orthanc":"orthanc"}')
        .with_env("ORTHANC__AUTHENTICATION_ENABLED", "true")
    )
    container.start()
    try:
        try:
            wait_for_logs(container, "Orthanc has started", timeout=60)
        except TimeoutError:
            # Some Orthanc images log a different startup line; fall through to
            # the polling-based readiness check in the orthanc_url fixture.
            pass
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def orthanc_url(orthanc_container: DockerContainer) -> str:
    host = orthanc_container.get_container_host_ip()
    port = orthanc_container.get_exposed_port(8042)
    url = f"http://{host}:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/system", auth=("orthanc", "orthanc"), timeout=2)
            if r.status_code == 200:
                return url
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("Orthanc did not become reachable")


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def configure_settings(database_url: str, orthanc_url: str) -> Iterator[None]:
    """Override settings via env so the FastAPI app under test sees test infra."""
    old: dict[str, str | None] = {}
    overrides = {
        "DATABASE_URL": database_url,
        "ORTHANC_URL": orthanc_url,
        "ORTHANC_USER": "orthanc",
        "ORTHANC_PASSWORD": "orthanc",
    }
    for k, v in overrides.items():
        old[k] = os.environ.get(k)
        os.environ[k] = v

    from app.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()

    yield

    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


@pytest.fixture
def db_session(database_url: str):
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s
        s.rollback()
    with engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE TABLE audit_events RESTART IDENTITY")
    engine.dispose()


@pytest_asyncio.fixture
async def api_client(orthanc_url: str) -> AsyncIterator[httpx.AsyncClient]:
    from app.main import create_app

    async with httpx.AsyncClient(base_url=orthanc_url, auth=("orthanc", "orthanc")) as oc:
        r = await oc.get("/studies")
        for sid in r.json():
            await oc.delete(f"/studies/{sid}")

    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
