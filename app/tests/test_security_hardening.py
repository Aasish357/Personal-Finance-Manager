"""Rate limiting and the production misconfiguration warnings on /health."""
import pytest

from app.core.rate_limit import RateLimiter
from app.core.security import DUMMY_HASH, Security


# --- the limiter itself -----------------------------------------------------

def test_allows_up_to_the_limit_then_blocks():
    limiter = RateLimiter(max_attempts=3, window_seconds=60)
    key = "ip:someone@example.com"

    for _ in range(3):
        assert limiter.is_blocked(key) == (False, 0)
        limiter.record_failure(key)

    blocked, retry_after = limiter.is_blocked(key)
    assert blocked is True
    assert 0 < retry_after <= 60


def test_success_resets_the_counter():
    limiter = RateLimiter(max_attempts=3, window_seconds=60)
    key = "ip:someone@example.com"
    for _ in range(2):
        limiter.record_failure(key)

    limiter.reset(key)

    assert limiter.is_blocked(key) == (False, 0)


def test_keys_are_independent():
    limiter = RateLimiter(max_attempts=2, window_seconds=60)
    for _ in range(2):
        limiter.record_failure("ip:a@example.com")

    assert limiter.is_blocked("ip:a@example.com")[0] is True
    assert limiter.is_blocked("ip:b@example.com") == (False, 0)


def test_entries_expire_after_the_window():
    limiter = RateLimiter(max_attempts=1, window_seconds=0)
    limiter.record_failure("ip:x")
    # A zero-length window means the single failure is already stale.
    assert limiter.is_blocked("ip:x")[0] is False


# --- the login endpoint -----------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_limiter():
    from app.core.rate_limit import login_limiter
    login_limiter._hits.clear()
    yield
    login_limiter._hits.clear()


def test_login_blocks_after_repeated_failures(client):
    for _ in range(5):
        response = client.post("/api/v1/auth/login", json={
            "email": "victim@example.com", "password": "wrong-guess"})
        assert response.status_code == 401

    blocked = client.post("/api/v1/auth/login", json={
        "email": "victim@example.com", "password": "wrong-guess"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_correct_password_still_works_before_the_limit(client):
    client.post("/api/v1/auth/register", json={
        "name": "Real", "email": "real@example.com", "password": "password123"})
    client.post("/api/v1/auth/login", json={
        "email": "real@example.com", "password": "nope"})

    response = client.post("/api/v1/auth/login", json={
        "email": "real@example.com", "password": "password123"})
    assert response.status_code == 200


def test_unknown_email_and_wrong_password_are_indistinguishable(client):
    """Both must return the same 401 body, so accounts can't be enumerated."""
    client.post("/api/v1/auth/register", json={
        "name": "Real", "email": "real@example.com", "password": "password123"})

    unknown = client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com", "password": "password123"})
    wrong = client.post("/api/v1/auth/login", json={
        "email": "real@example.com", "password": "definitely-not-it"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


# --- /health warnings -------------------------------------------------------

def test_health_warns_when_secret_key_is_the_dev_default(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "secret_key", "dev-secret-key-change-me")

    body = client.get("/health").json()
    assert any("SECRET_KEY" in w for w in body["warnings"])
    assert body["status"] == "degraded"


def test_health_is_ok_with_a_real_secret(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "secret_key", "a-real-looking-secret")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example.com")

    body = client.get("/health").json()
    assert body["warnings"] == []
    assert body["status"] == "ok"


def test_dummy_hash_is_a_valid_bcrypt_hash():
    """The timing-equaliser must be a real hash, or verify would short-circuit."""
    assert Security.verify_password("anything", DUMMY_HASH) is False