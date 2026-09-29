"""
Tests run against a throwaway SQLite database by default, which is fast and
needs no credentials.

To run them against a real Postgres/Supabase instance, point TEST_DATABASE_URL
at a database that exists *for testing*:

    TEST_DATABASE_URL="postgresql://user:pass@host:5432/finance_test" pytest

Safety: the suite calls drop_all() before every test, because tests need a
known-clean schema. That is destructive, so pointing TEST_DATABASE_URL at a
production database would wipe it. The guard below refuses to run unless the
database name looks like a test database, or ALLOW_TEST_DB_RESET=1 is set
explicitly.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db import base  # noqa: F401  registers models
from app.db.database import Base, get_db, normalise_database_url
from app.main import app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_finance.db")

_is_sqlite = TEST_DATABASE_URL.startswith("sqlite")

if not _is_sqlite:
    # drop_all() below is destructive; make pointing it at a real database an
    # explicit, deliberate act rather than a copy-paste accident.
    _db_name = (make_url(normalise_database_url(TEST_DATABASE_URL)).database or "").lower()
    _looks_like_a_test_db = "test" in _db_name
    if not _looks_like_a_test_db and os.environ.get("ALLOW_TEST_DB_RESET") != "1":
        sys.exit(
            f"\n\nREFUSING TO RUN: TEST_DATABASE_URL points at database "
            f"'{_db_name or '<unnamed>'}', which does not look like a test database.\n"
            f"This suite calls drop_all() before every test and would DESTROY that "
            f"database's data.\n\n"
            f"  Do one of:\n"
            f"    - point TEST_DATABASE_URL at a scratch database "
            f"(e.g. '.../finance_test')\n"
            f"    - or set ALLOW_TEST_DB_RESET=1 if you really mean it\n\n"
        )

# Same URL handling the app uses, so a bare `postgresql://` string resolves to
# the psycopg 3 driver here too instead of failing with "No module named
# psycopg2".
engine = create_engine(
    normalise_database_url(TEST_DATABASE_URL),
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Registers and logs in a fresh user, returns Authorization headers for it."""
    client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": "auth-fixture@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "auth-fixture@example.com", "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
