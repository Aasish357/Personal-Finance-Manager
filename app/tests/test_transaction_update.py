"""PATCH /transactions/{id} -- editing must keep budget alerts honest."""


def _mk_category(client, headers, name):
    r = client.post("/api/v1/categories", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _budget(client, headers, category_id, month, amount):
    r = client.post("/api/v1/budgets",
                    json={"category_id": category_id, "month": month, "amount": amount},
                    headers=headers)
    assert r.status_code == 201, r.text


def _spend(client, headers, category_id, amount, date):
    r = client.post("/api/v1/transactions", json={
        "amount": amount, "transaction_type": "expense", "category_id": category_id,
        "transaction_date": date}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _alerts(client, headers):
    return client.get("/api/v1/alerts", headers=headers).json()


def _patch(client, headers, tid, payload):
    return client.patch(f"/api/v1/transactions/{tid}", json=payload, headers=headers)


def test_patch_updates_only_the_fields_sent(client, auth_headers):
    cid = _mk_category(client, auth_headers, "Food")
    tid = _spend(client, auth_headers, cid, 10, "2024-10-05T00:00:00")

    resp = _patch(client, auth_headers, tid, {"amount": 25, "description": "corrected"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["amount"] == 25
    assert body["description"] == "corrected"
    # untouched fields survive
    assert body["category_id"] == cid
    assert body["transaction_date"].startswith("2024-10-05")


def test_patch_can_clear_the_category(client, auth_headers):
    tid = _spend(client, auth_headers, _mk_category(client, auth_headers, "Food"), 10, "2024-10-05T00:00:00")
    resp = _patch(client, auth_headers, tid, {"category_id": None})
    assert resp.status_code == 200
    assert resp.json()["category_id"] is None


def test_patch_rejects_a_category_the_caller_does_not_own(client, auth_headers):
    """A category id that isn't the caller's must be refused, not silently accepted."""
    tid = _spend(client, auth_headers, _mk_category(client, auth_headers, "Mine"), 10, "2024-10-05T00:00:00")
    resp = _patch(client, auth_headers, tid, {"category_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 404


def test_patch_rejects_non_positive_amount(client, auth_headers):
    tid = _spend(client, auth_headers, _mk_category(client, auth_headers, "Food"), 10, "2024-10-05T00:00:00")
    assert _patch(client, auth_headers, tid, {"amount": 0}).status_code == 422
    assert _patch(client, auth_headers, tid, {"amount": -5}).status_code == 422


def test_patch_missing_transaction_is_404(client, auth_headers):
    assert _patch(client, auth_headers, "nope", {"amount": 5}).status_code == 404


def test_patch_requires_auth(client, auth_headers):
    tid = _spend(client, auth_headers, _mk_category(client, auth_headers, "Food"), 10, "2024-10-05T00:00:00")
    assert client.patch(f"/api/v1/transactions/{tid}", json={"amount": 5}).status_code == 401


def test_lowering_an_amount_resolves_the_alert(client, auth_headers):
    """The whole point of reconciliation: an edit can undo an overspend."""
    cid = _mk_category(client, auth_headers, "Groceries")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 100)
    tid = _spend(client, auth_headers, cid, 95, "2024-10-05T00:00:00")
    assert [a["status"] for a in _alerts(client, auth_headers)] == ["active"]

    _patch(client, auth_headers, tid, {"amount": 20})

    alerts = _alerts(client, auth_headers)
    assert [a["status"] for a in alerts] == ["resolved"]
    assert client.get("/api/v1/analytics/overview", headers=auth_headers).json()["active_alerts"] == 0


def test_moving_spend_to_another_category_resolves_the_old_alert(client, auth_headers):
    food = _mk_category(client, auth_headers, "Food")
    fun = _mk_category(client, auth_headers, "Fun")
    _budget(client, auth_headers, food, "2024-10-01T00:00:00", 100)
    tid = _spend(client, auth_headers, food, 95, "2024-10-05T00:00:00")

    resp = _patch(client, auth_headers, tid, {"category_id": fun})
    assert resp.status_code == 200

    # The Food alert must stand down even though the transaction still exists.
    food_alerts = [a for a in _alerts(client, auth_headers) if a["category_id"] == food]
    assert [a["status"] for a in food_alerts] == ["resolved"]


def test_raising_an_amount_raises_a_new_threshold(client, auth_headers):
    cid = _mk_category(client, auth_headers, "Groceries")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 100)
    tid = _spend(client, auth_headers, cid, 10, "2024-10-05T00:00:00")
    assert _alerts(client, auth_headers) == []

    _patch(client, auth_headers, tid, {"amount": 95})

    assert [a["threshold"] for a in _alerts(client, auth_headers)] == ["90%"]