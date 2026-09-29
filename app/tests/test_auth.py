import pytest


@pytest.mark.parametrize(
    "user_data, expected_status",
    [
        ({"name": "Test User", "email": "new-user@example.com", "password": "password123"}, 201),
        ({"name": "", "email": "test@example.com", "password": "password123"}, 422),
        ({"name": "Test User", "email": "not-an-email", "password": "password123"}, 422),
        ({"name": "Test User", "email": "test@example.com", "password": "short"}, 422),
    ],
)
def test_register(client, user_data, expected_status):
    response = client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == expected_status


def test_register_duplicate_email_rejected(client):
    payload = {"name": "Test User", "email": "dupe@example.com", "password": "password123"}
    first = client.post("/api/v1/auth/register", json=payload)
    second = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 400


def test_login_returns_token(client):
    client.post(
        "/api/v1/auth/register",
        json={"name": "Login User", "email": "login@example.com", "password": "password123"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/register",
        json={"name": "Login User", "email": "wrongpass@example.com", "password": "password123"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "not-the-password"},
    )
    assert response.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "auth-fixture@example.com"
