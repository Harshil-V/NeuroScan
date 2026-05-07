"""Integration-test-scoped fixtures.

Adds an autouse cleanup so every integration test starts with empty tables,
regardless of whether it requests ``db_session``.
The session-scoped ``configure_settings`` fixture creates the schema once;
the per-test ``api_client`` fixture clears Orthanc state. This fixture
covers the database side for tests that don't take ``db_session``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine


@pytest.fixture(autouse=True)
def _truncate_audit_events(database_url: str) -> Iterator[None]:
    yield
    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "TRUNCATE TABLE audit_events, reconstruction_jobs RESTART IDENTITY"
            )
    finally:
        engine.dispose()
