"""
Tests run against a throwaway SQLite database by default, which is fast and
needs no credentials. Set TEST_DATABASE_URL to run them against a real
Postgres/Supabase instance instead (useful for verifying migrations):

    TEST_DATABASE_URL="postgresql://user:pass@host:5432/db" pytest
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import base  # noqa: F401  registers models
from app.db.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_finance.db")

_is_sqlite = TEST_DATABASE_URL.startswith("sqlite")
engine = create_engine(
    TEST_DATABASE_URL,
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
