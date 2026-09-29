def _make_category(client, headers, name="Groceries"):
    resp = client.post("/api/v1/categories", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_transaction_over_budget_triggers_alert(client, auth_headers):
    category_id = _make_category(client, auth_headers)

    budget_resp = client.post(
        "/api/v1/budgets",
        json={"category_id": category_id, "month": "2024-10-01T00:00:00", "amount": 100},
        headers=auth_headers,
    )
    assert budget_resp.status_code == 201

    # Spend past the budget within the same month/category.
    tx_resp = client.post(
        "/api/v1/transactions",
        json={
            "amount": 120,
            "transaction_type": "expense",
            "description": "Big grocery run",
            "merchant": "Market",
            "category_id": category_id,
            "transaction_date": "2024-10-15T00:00:00",
        },
        headers=auth_headers,
    )
    assert tx_resp.status_code == 201

    alerts_resp = client.get("/api/v1/alerts", headers=auth_headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) == 1
    assert alerts[0]["threshold"] == "100%"


def test_transaction_under_budget_triggers_no_alert(client, auth_headers):
    category_id = _make_category(client, auth_headers, name="Rent")
    client.post(
        "/api/v1/budgets",
        json={"category_id": category_id, "month": "2024-11-01T00:00:00", "amount": 1000},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "amount": 50,
            "transaction_type": "expense",
            "description": "Small purchase",
            "merchant": "Shop",
            "category_id": category_id,
            "transaction_date": "2024-11-05T00:00:00",
        },
        headers=auth_headers,
    )
    alerts = client.get("/api/v1/alerts", headers=auth_headers).json()
    assert alerts == []


def test_overview_reflects_transactions(client, auth_headers):
    client.post(
        "/api/v1/transactions",
        json={
            "amount": 3000,
            "transaction_type": "income",
            "description": "Paycheck",
            "merchant": "Employer",
            "transaction_date": "2024-11-01T00:00:00",
        },
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "amount": 500,
            "transaction_type": "expense",
            "description": "Bills",
            "merchant": "Utility Co",
            "transaction_date": "2024-11-02T00:00:00",
        },
        headers=auth_headers,
    )
    overview = client.get("/api/v1/analytics/overview", headers=auth_headers).json()
    assert overview["total_income"] == 3000
    assert overview["total_expense"] == 500
    assert overview["balance"] == 2500
