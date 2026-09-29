"""Categories must be private to their owner. These tests pin down the isolation
that used to be missing: categories were a single global table, so any
authenticated user could list and delete everyone else's.
"""
import pytest


@pytest.fixture
def other_user(client):
    """A second registered user, returned with its own auth headers."""
    client.post("/api/v1/auth/register", json={
        "name": "Other", "email": "other-user@example.com", "password": "password123"})
    token = client.post("/api/v1/auth/login", json={
        "email": "other-user@example.com", "password": "password123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _mk(client, headers, name):
    return client.post("/api/v1/categories", json={"name": name}, headers=headers).json()["id"]


def test_category_list_is_scoped_to_the_caller(client, auth_headers, other_user):
    _mk(client, auth_headers, "Mine")

    assert [c["name"] for c in client.get("/api/v1/categories", headers=auth_headers).json()] == ["Mine"]
    assert client.get("/api/v1/categories", headers=other_user).json() == []


def test_two_users_may_each_have_the_same_category_name(client, auth_headers, other_user):
    assert client.post("/api/v1/categories", json={"name": "Groceries"}, headers=auth_headers).status_code == 201
    assert client.post("/api/v1/categories", json={"name": "Groceries"}, headers=other_user).status_code == 201


def test_duplicate_name_within_one_user_rejected(client, auth_headers):
    _mk(client, auth_headers, "Rent")
    assert client.post("/api/v1/categories", json={"name": "Rent"}, headers=auth_headers).status_code == 400


def test_cannot_delete_another_users_category(client, auth_headers, other_user):
    cid = _mk(client, auth_headers, "Private")
    assert client.delete(f"/api/v1/categories/{cid}", headers=other_user).status_code == 404
    # Still there for its real owner.
    assert [c["name"] for c in client.get("/api/v1/categories", headers=auth_headers).json()] == ["Private"]


def test_cannot_create_budget_against_another_users_category(client, auth_headers, other_user):
    cid = _mk(client, auth_headers, "Private")
    resp = client.post("/api/v1/budgets",
                       json={"category_id": cid, "month": "2024-10-01T00:00:00", "amount": 100},
                       headers=other_user)
    assert resp.status_code == 404


def test_cannot_create_transaction_against_another_users_category(client, auth_headers, other_user):
    cid = _mk(client, auth_headers, "Private")
    resp = client.post("/api/v1/transactions", json={
        "amount": 10, "transaction_type": "expense", "category_id": cid,
        "transaction_date": "2024-10-01T00:00:00"}, headers=other_user)
    assert resp.status_code == 404


def test_analytics_never_leaks_another_users_category_name(client, auth_headers, other_user):
    """budget-vs-actual resolves category names; it must only resolve the
    caller's own."""
    _mk(client, other_user, "SecretProject")
    client.post("/api/v1/transactions", json={
        "amount": 100, "transaction_type": "expense",
        "transaction_date": "2024-10-01T00:00:00"}, headers=auth_headers)

    body = client.get("/api/v1/analytics/categories", headers=auth_headers).text
    assert "SecretProject" not in body


def test_deleting_user_cascades_to_their_categories(client, auth_headers):
    """Categories hang off the user, so deleting the user must take them too.

    Uses the test session factory directly -- the app's own SessionLocal
    points at the real DATABASE_URL, not the throwaway test database.
    """
    from app.db.models.category import Category
    from app.db.models.user import User
    from app.tests.conftest import TestingSessionLocal

    cid = _mk(client, auth_headers, "Doomed")
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "auth-fixture@example.com").first()
        assert user is not None
        db.delete(user)
        db.commit()
        assert db.query(Category).filter(Category.id == cid).first() is None
    finally:
        db.close()