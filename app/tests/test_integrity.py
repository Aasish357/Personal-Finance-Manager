"""Regression tests for the data-integrity fixes (stale alerts, guarded deletes)."""


def _mk_category(client, headers, name):
    r = client.post("/api/v1/categories", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _budget(client, headers, category_id, month, amount):
    r = client.post("/api/v1/budgets",
                    json={"category_id": category_id, "month": month, "amount": amount},
                    headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _spend(client, headers, category_id, amount, date):
    r = client.post("/api/v1/transactions", json={
        "amount": amount, "transaction_type": "expense", "description": "spend",
        "category_id": category_id, "transaction_date": date}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _alerts(client, headers):
    return client.get("/api/v1/alerts", headers=headers).json()


# --- stale alerts on delete -------------------------------------------------

def test_deleting_spend_resolves_alert(client, auth_headers):
    """The bug: removing the spend must stand the alert down, not leave it active."""
    cid = _mk_category(client, auth_headers, "Groceries")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 100)
    tx_id = _spend(client, auth_headers, cid, 95, "2024-10-15T00:00:00")

    assert [(a["threshold"], a["status"]) for a in _alerts(client, auth_headers)] == [("90%", "active")]

    assert client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers).status_code == 204

    alerts = _alerts(client, auth_headers)
    assert [(a["threshold"], a["status"]) for a in alerts] == [("90%", "resolved")]
    # And the overview must agree that nothing is active any more.
    assert client.get("/api/v1/analytics/overview", headers=auth_headers).json()["active_alerts"] == 0


def test_alert_re_raises_after_spend_is_restored(client, auth_headers):
    """A resolved alert must not permanently block a genuine re-crossing."""
    cid = _mk_category(client, auth_headers, "Dining")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 100)
    tx_id = _spend(client, auth_headers, cid, 95, "2024-10-05T00:00:00")
    client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
    _spend(client, auth_headers, cid, 95, "2024-10-06T00:00:00")

    ninety = [a for a in _alerts(client, auth_headers) if a["threshold"] == "90%"]
    assert any(a["status"] == "active" for a in ninety), _alerts(client, auth_headers)


def test_dismissed_alert_does_not_re_raise(client, auth_headers):
    """A user-acknowledged alert stays put; we must not nag them again."""
    cid = _mk_category(client, auth_headers, "Travel")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 100)
    _spend(client, auth_headers, cid, 80, "2024-10-05T00:00:00")

    alert = _alerts(client, auth_headers)[0]
    assert alert["threshold"] == "75%"
    client.post(f"/api/v1/alerts/{alert['id']}/dismiss", headers=auth_headers)

    _spend(client, auth_headers, cid, 10, "2024-10-06T00:00:00")  # 90%, a new threshold

    seventy_five = [a for a in _alerts(client, auth_headers) if a["threshold"] == "75%"]
    assert [a["status"] for a in seventy_five] == ["dismissed"]


def test_deleting_income_does_not_touch_alerts(client, auth_headers):
    cid = _mk_category(client, auth_headers, "Bills")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 100)
    _spend(client, auth_headers, cid, 95, "2024-10-05T00:00:00")
    income = client.post("/api/v1/transactions", json={
        "amount": 500, "transaction_type": "income", "description": "Paycheck",
        "transaction_date": "2024-10-06T00:00:00"}, headers=auth_headers).json()["id"]

    client.delete(f"/api/v1/transactions/{income}", headers=auth_headers)

    assert [a["status"] for a in _alerts(client, auth_headers)] == ["active"]


# --- category deletion ------------------------------------------------------

def test_delete_in_use_category_is_409_not_500(client, auth_headers):
    """The bug: this used to raise IntegrityError and return a 500."""
    cid = _mk_category(client, auth_headers, "Utilities")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 100)
    _spend(client, auth_headers, cid, 10, "2024-10-05T00:00:00")

    resp = client.delete(f"/api/v1/categories/{cid}", headers=auth_headers)
    assert resp.status_code == 409, resp.text
    assert "Utilities" in resp.json()["detail"]
    # Still there, and still usable.
    assert client.get("/api/v1/categories", headers=auth_headers).status_code == 200


def test_delete_unused_category_succeeds(client, auth_headers):
    cid = _mk_category(client, auth_headers, "Unused")
    assert client.delete(f"/api/v1/categories/{cid}", headers=auth_headers).status_code == 204


def test_delete_missing_category_is_404(client, auth_headers):
    assert client.delete("/api/v1/categories/does-not-exist", headers=auth_headers).status_code == 404


# --- budget uniqueness ------------------------------------------------------

def test_duplicate_budget_same_month_is_409(client, auth_headers):
    cid = _mk_category(client, auth_headers, "Rent")
    _budget(client, auth_headers, cid, "2024-10-01T00:00:00", 1000)

    dup = client.post("/api/v1/budgets",
                      json={"category_id": cid, "month": "2024-10-01T00:00:00", "amount": 555},
                      headers=auth_headers)
    assert dup.status_code == 409, dup.text
    assert len(client.get("/api/v1/budgets", headers=auth_headers).json()) == 1


def test_budget_allowed_in_different_months_and_categories(client, auth_headers):
    a = _mk_category(client, auth_headers, "Rent")
    b = _mk_category(client, auth_headers, "Food")
    _budget(client, auth_headers, a, "2024-10-01T00:00:00", 1000)
    _budget(client, auth_headers, a, "2024-11-01T00:00:00", 1000)
    _budget(client, auth_headers, b, "2024-10-01T00:00:00", 200)
    assert len(client.get("/api/v1/budgets", headers=auth_headers).json()) == 3