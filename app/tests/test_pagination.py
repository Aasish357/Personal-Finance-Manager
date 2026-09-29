"""
Pagination on GET /transactions.

The response must stay a bare JSON array (existing callers depend on that);
the unpaginated total rides in X-Total-Count.
"""


def _seed(client, headers, count):
    """Create `count` expenses on distinct days so ordering is unambiguous."""
    for i in range(count):
        assert client.post("/api/v1/transactions", json={
            "amount": 10 + i, "transaction_type": "expense",
            "transaction_date": f"2024-01-{i + 1:02d}T00:00:00"},
            headers=headers).status_code == 201


def test_no_params_still_returns_everything(client, auth_headers):
    """Backward compatibility: omitting limit/offset must not truncate."""
    _seed(client, auth_headers, 12)
    rows = client.get("/api/v1/transactions", headers=auth_headers).json()
    assert isinstance(rows, list)
    assert len(rows) == 12


def test_total_count_header_reflects_all_rows(client, auth_headers):
    _seed(client, auth_headers, 12)
    resp = client.get("/api/v1/transactions?limit=5", headers=auth_headers)
    assert len(resp.json()) == 5
    assert resp.headers["x-total-count"] == "12"


def test_limit_and_offset_page_through_results(client, auth_headers):
    _seed(client, auth_headers, 12)

    page1 = client.get("/api/v1/transactions?limit=5&offset=0", headers=auth_headers).json()
    page2 = client.get("/api/v1/transactions?limit=5&offset=5", headers=auth_headers).json()
    page3 = client.get("/api/v1/transactions?limit=5&offset=10", headers=auth_headers).json()

    assert [len(p) for p in (page1, page2, page3)] == [5, 5, 2]
    ids = [t["id"] for p in (page1, page2, page3) for t in p]
    assert len(set(ids)) == 12  # no duplicates, no gaps
    # Newest first: the last day seeded (amount 21) comes first.
    assert page1[0]["amount"] == 21


def test_offset_past_the_end_returns_empty(client, auth_headers):
    _seed(client, auth_headers, 3)
    resp = client.get("/api/v1/transactions?limit=5&offset=99", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["x-total-count"] == "3"


def test_total_respects_active_filters(client, auth_headers):
    cid = client.post("/api/v1/categories", json={"name": "Food"}, headers=auth_headers).json()["id"]
    for i in range(3):
        client.post("/api/v1/transactions", json={
            "amount": 10, "transaction_type": "expense", "category_id": cid,
            "transaction_date": f"2024-01-0{i + 1}T00:00:00"}, headers=auth_headers)
    for i in range(4):
        client.post("/api/v1/transactions", json={
            "amount": 10, "transaction_type": "income",
            "transaction_date": f"2024-02-0{i + 1}T00:00:00"}, headers=auth_headers)

    by_cat = client.get(f"/api/v1/transactions?category_id={cid}", headers=auth_headers)
    by_type = client.get("/api/v1/transactions?transaction_type=income", headers=auth_headers)

    assert len(by_cat.json()) == 3
    assert by_cat.headers["x-total-count"] == "3"
    assert by_type.headers["x-total-count"] == "4"


def test_invalid_paging_is_rejected(client, auth_headers):
    assert client.get("/api/v1/transactions?limit=0", headers=auth_headers).status_code == 422
    assert client.get("/api/v1/transactions?offset=-1", headers=auth_headers).status_code == 422
    assert client.get("/api/v1/transactions?limit=9999", headers=auth_headers).status_code == 422


def test_paging_does_not_leak_other_users_rows(client, auth_headers):
    client.post("/api/v1/auth/register", json={
        "name": "Other", "email": "pg-other@example.com", "password": "password123"})
    other = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={
        "email": "pg-other@example.com", "password": "password123"}).json()["access_token"]}

    _seed(client, auth_headers, 3)
    _seed(client, other, 7)

    mine = client.get("/api/v1/transactions", headers=auth_headers)
    assert len(mine.json()) == 3
    assert mine.headers["x-total-count"] == "3"


def test_paging_requires_auth(client, auth_headers):
    assert client.get("/api/v1/transactions").status_code == 401