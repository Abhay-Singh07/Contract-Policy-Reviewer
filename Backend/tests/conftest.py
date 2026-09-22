"""
Shared fixtures. The key trick: we redirect DATABASE_URL to a dedicated
`<db>_test` database BEFORE any `app.*` module is imported, since
app/db/database.py builds its engine at import time from app/config.py's
settings. That's why the redirect happens at the very top of this file,
above every other import.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import dotenv_values

_env_path = Path(__file__).resolve().parents[1] / ".env"
_env = dotenv_values(_env_path) if _env_path.exists() else {}
_base_url = (
    _env.get("DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql://postgres:postgres@localhost:5432/contract_reviewer"
)

_parsed = urlparse(_base_url)
TEST_DB_NAME = _parsed.path.lstrip("/") + "_test"
TEST_DATABASE_URL = urlunparse(_parsed._replace(path=f"/{TEST_DB_NAME}"))

os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # must happen before any app import below

import pytest  # noqa: E402
import sqlalchemy  # noqa: E402
from sqlalchemy import event, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.state import ClauseState  # noqa: E402
from app.db.database import Base, engine  # noqa: E402
from app.db import models  # noqa: E402  (registers all tables on Base)
from app.core.auth import verify_api_key  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


def _ensure_test_database_exists() -> None:
    admin_url = urlunparse(_parsed._replace(path="/postgres"))
    admin_engine = sqlalchemy.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    """Runs once per test session: creates the test DB, the pgvector extension, and all tables."""
    _ensure_test_database_exists()
    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def db():
    """A DB session scoped to one test. Wraps everything in an outer transaction that's
    always rolled back at the end — so even code that calls session.commit() internally
    (like app/db/crud.py) never actually persists anything past this test.

    This is SQLAlchemy's standard "join a session into an external transaction" pattern:
    an outer transaction plus a SAVEPOINT that gets restarted after each inner commit.
    """
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture()
def clean_tables():
    """For tests that go through the API (which opens its own DB session per request,
    outside the `db` fixture's transaction) — truncates everything before the test runs."""
    with engine.connect() as conn:
        conn.execute(text(
            "TRUNCATE documents, clauses, findings, reports, regulation_sections RESTART IDENTITY CASCADE;"
        ))
        conn.commit()
    yield


@pytest.fixture()
def indemnity_clause() -> ClauseState:
    return ClauseState(
        clause_number=2, heading="Indemnity",
        text="The Vendor shall indemnify the Client against all claims, without limit.",
    )


@pytest.fixture(autouse=True)
def _bypass_api_key_auth():
    """Most tests aren't testing auth itself, and shouldn't fail just because the
    developer has a real API_KEY set in their local .env for manual testing.
    test_auth.py explicitly pops this override for the handful of tests that
    need to exercise real enforcement."""
    fastapi_app.dependency_overrides[verify_api_key] = lambda: None
    yield
    fastapi_app.dependency_overrides.pop(verify_api_key, None)