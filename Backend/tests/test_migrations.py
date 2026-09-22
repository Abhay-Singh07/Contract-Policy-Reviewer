"""
The rest of the test suite uses Base.metadata.create_all() for speed (see
conftest.py's _test_schema fixture) — which completely bypasses Alembic.
That's fine for testing application logic, but it means a broken migration
file (bad import, wrong column type, missing extension setup) would never
be caught by `pytest` alone.

These tests run the REAL `alembic` CLI as a subprocess against a dedicated,
fully disposable database — this is the only way to catch that class of bug.
Runs in its own throwaway DB (not the shared "_test" one) so upgrading/
downgrading real tables here can never interfere with other tests.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
import sqlalchemy
from sqlalchemy import text

from tests.conftest import _base_url as _shared_base_url

BACKEND_DIR = Path(__file__).resolve().parents[1]

_parsed = urlparse(_shared_base_url)
MIGRATIONS_DB_NAME = _parsed.path.lstrip("/") + "_migrations_test"
MIGRATIONS_DB_URL = urlunparse(_parsed._replace(path=f"/{MIGRATIONS_DB_NAME}"))


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": MIGRATIONS_DB_URL}
    return subprocess.run(
        ["alembic", *args], cwd=BACKEND_DIR, env=env,
        capture_output=True, text=True,
    )


@pytest.fixture()
def migrations_db():
    """Creates a throwaway database for this test only, drops it afterward."""
    admin_url = urlunparse(_parsed._replace(path="/postgres"))
    admin_engine = sqlalchemy.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATIONS_DB_NAME}"'))
        conn.execute(text(f'CREATE DATABASE "{MIGRATIONS_DB_NAME}"'))
    admin_engine.dispose()

    yield MIGRATIONS_DB_URL

    admin_engine = sqlalchemy.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATIONS_DB_NAME}"'))
    admin_engine.dispose()


def test_alembic_upgrade_head_creates_all_tables(migrations_db):
    """This is what would have caught the missing pgvector import — a broken
    migration makes this subprocess exit non-zero."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr

    engine = sqlalchemy.create_engine(migrations_db)
    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ))}
    engine.dispose()

    assert {"documents", "clauses", "findings", "reports",
            "regulation_sections", "alembic_version"} <= tables


def test_regulation_sections_embedding_column_is_real_vector_type(migrations_db):
    """Confirms the column didn't silently fall back to some other type —
    Postgres reports pgvector's custom type as 'USER-DEFINED'."""
    assert _run_alembic("upgrade", "head").returncode == 0

    engine = sqlalchemy.create_engine(migrations_db)
    with engine.connect() as conn:
        col_type = conn.execute(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='regulation_sections' AND column_name='embedding'"
        )).scalar()
    engine.dispose()

    assert col_type == "USER-DEFINED"


def test_alembic_downgrade_then_upgrade_round_trips_cleanly(migrations_db):
    assert _run_alembic("upgrade", "head").returncode == 0
    assert _run_alembic("downgrade", "base").returncode == 0

    engine = sqlalchemy.create_engine(migrations_db)
    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ))}
    engine.dispose()
    assert "documents" not in tables  # downgrade actually dropped the app tables

    assert _run_alembic("upgrade", "head").returncode == 0