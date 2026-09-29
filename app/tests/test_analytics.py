"""
Analytics is now aggregated in SQL. These tests pin the results to exact
values so the rewrite cannot silently change a number the dashboard shows.
"""
from datetime import datetime, timedelta, timezone

import pytest

TODAY = datetime.now(timezone.utc)
THIS_MONTH = TODAY.strftime("%Y-%m")
LAST_MONTH = (TODAY.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def _tx(client, headers, amount, kind, date, category_id=None):
    r = client.post("/api/v1/transactions", json={
        "amount": amount, "transaction_type": kind, "category_id": category_id,
        "transaction_date": date}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_monthly_groups_by_calendar_month(client, auth_headers):
    _tx(client, auth_headers, 1000, "income", "2024-03-02T00:00:00")
    _tx(client, auth_headers, 250, "expense", "2024-03-15T00:00:00")
    _tx(client, auth_headers, 400, "income", "2024-04-01T00:00:00")

    rows = client.get("/api/v1/analytics/monthly", headers=auth_headers).json()

    assert rows == [
        {"month": "2024-03", "income": 1000.0, "expense": 250.0, "net": 750.0},
        {"month": "2024-04", "income": 400.0, "expense": 0.0, "net": 400.0},
    ]


def test_monthly_is_oldest_first(client, auth_headers):
    _tx(client, auth_headers, 10, "expense", "2024-06-01T00:00:00")
    _tx(client, auth_headers, 10, "expense", "2024-01-01T00:00:00")
    months = [r["month"] for r in client.get("/api/v1/analytics/monthly", headers=auth_headers).json()]
    assert months == sorted(months)


def test_monthly_excludes_other_users_transactions(client, auth_headers):
    client.post("/api/v1/auth/register", json={
        "name": "Other", "email": "m-other@example.com", "password": "password123"})
    other = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={
        "email": "m-other@example.com", "password": "password123"}).json()["access_token"]}

    _tx(client, auth_headers, 100, "income", "2024-03-01T00:00:00")
    _tx(client, other, 9999, "income", "2024-03-01T00:00:00")

    rows = client.get("/api/v1/analytics/monthly", headers=auth_headers).json()
    assert [r["income"] for r in rows] == [100.0]


def test_category_percentages_sum_to_100(client, auth_headers):
    cid = client.post("/api/v1/categories", json={"name": "Food"}, headers=auth_headers).json()["id"]
    _tx(client, auth_headers, 300, "expense", "2024-05-01T00:00:00", cid)
    _tx(client, auth_headers, 100, "expense", "2024-05-02T00:00:00")  # uncategorized

    rows = client.get("/api/v1/analytics/categories", headers=auth_headers).json()

    assert rows[0]["category_name"] == "Food"
    assert rows[0]["percentage"] == 75.0
    assert rows[1]["category_name"] == "Uncategorized"
    assert round(sum(r["percentage"] for r in rows), 1) == 100.0


def test_category_analytics_ignores_income(client, auth_headers):
    _tx(client, auth_headers, 5000, "income", "2024-05-01T00:00:00")
    assert client.get("/api/v1/analytics/categories", headers=auth_headers).json() == []


def test_budget_vs_actual_matches_across_categories_and_months(client, auth_headers):
    """The old implementation was O(budgets x transactions); this is the
    multi-budget, multi-month case that made that expensive."""
    food = client.post("/api/v1/categories", json={"name": "Food"}, headers=auth_headers).json()["id"]
    rent = client.post("/api/v1/categories", json={"name": "Rent"}, headers=auth_headers).json()["id"]
    for cat, month, amount in [
        (food, "2024-03-01T00:00:00", 300), (food, "2024-04-01T00:00:00", 200),
        (rent, "2024-03-01T00:00:00", 1200), (rent, "2024-04-01T00:00:00", 1200),
    ]:
        assert client.post("/api/v1/budgets",
                           json={"category_id": cat, "month": month, "amount": 1000},
                           headers=auth_headers).status_code == 201

    _tx(client, auth_headers, 300, "expense", "2024-03-10T00:00:00", food)
    _tx(client, auth_headers, 200, "expense", "2024-04-10T00:00:00", food)
    _tx(client, auth_headers, 1250, "expense", "2024-03-10T00:00:00", rent)

    rows = client.get("/api/v1/analytics/budget-vs-actual", headers=auth_headers).json()
    by_key = {(r["category_name"], r["month"]): r for r in rows}

    assert by_key[("Food", "2024-03")]["spent"] == 300.0
    assert by_key[("Food", "2024-03")]["utilization_pct"] == 30.0
    assert by_key[("Food", "2024-04")]["spent"] == 200.0
    # Rent overspent in March, untouched in April -- the two must not mix.
    assert by_key[("Rent", "2024-03")]["spent"] == 1250.0
    assert by_key[("Rent", "2024-03")]["utilization_pct"] == 125.0
    assert by_key[("Rent", "2024-04")]["spent"] == 0.0
    assert by_key[("Rent", "2024-04")]["utilization_pct"] == 0.0


def test_budget_vs_actual_sorts_newest_month_first(client, auth_headers):
    cid = client.post("/api/v1/categories", json={"name": "Food"}, headers=auth_headers).json()["id"]
    for month in ("2024-01-01T00:00:00", "2024-03-01T00:00:00", "2024-02-01T00:00:00"):
        client.post("/api/v1/budgets", json={"category_id": cid, "month": month, "amount": 100},
                    headers=auth_headers)
    months = [r["month"] for r in client.get("/api/v1/analytics/budget-vs-actual", headers=auth_headers).json()]
    assert months == ["2024-03", "2024-02", "2024-01"]


def test_overview_totals_and_count(client, auth_headers):
    _tx(client, auth_headers, 3000, "income", "2024-03-01T00:00:00")
    _tx(client, auth_headers, 500, "expense", "2024-03-02T00:00:00")
    _tx(client, auth_headers, 25, "expense", "2024-04-01T00:00:00")

    body = client.get("/api/v1/analytics/overview", headers=auth_headers).json()

    assert body["total_income"] == 3000.0
    assert body["total_expense"] == 525.0
    assert body["balance"] == 2475.0
    assert body["transaction_count"] == 3
    # Current month is empty, because the fixtures are in the past.
    assert body["current_month_income"] == 0.0
    assert body["current_month_expense"] == 0.0


def test_overview_current_month_window(client, auth_headers):
    """current_month_* must track the real current month, not all time."""
    in_this_month = TODAY.strftime("%Y-%m-%d")
    _tx(client, auth_headers, 700, "income", f"{in_this_month}T12:00:00")
    _tx(client, auth_headers, 3000, "income", "2020-01-01T00:00:00")

    body = client.get("/api/v1/analytics/overview", headers=auth_headers).json()

    assert body["current_month_income"] == 700.0
    assert body["total_income"] == 3700.0


def test_overview_counts_active_alerts_only(client, auth_headers):
    cid = client.post("/api/v1/categories", json={"name": "Food"}, headers=auth_headers).json()["id"]
    client.post("/api/v1/budgets", json={"category_id": cid, "month": "2024-03-01T00:00:00", "amount": 100},
                headers=auth_headers)
    _tx(client, auth_headers, 95, "expense", "2024-03-10T00:00:00", cid)

    assert client.get("/api/v1/analytics/overview", headers=auth_headers).json()["active_alerts"] == 1
    alert = client.get("/api/v1/alerts", headers=auth_headers).json()[0]
    client.post(f"/api/v1/alerts/{alert['id']}/dismiss", headers=auth_headers)
    assert client.get("/api/v1/analytics/overview", headers=auth_headers).json()["active_alerts"] == 0


def test_all_analytics_require_auth(client, auth_headers):
    cid = client.post("/api/v1/categories", json={"name": "Food"}, headers=auth_headers).json()["id"]
    _tx(client, auth_headers, 50, "expense", "2024-03-01T00:00:00", cid)
    for path in ("/overview", "/monthly", "/categories", "/budget-vs-actual"):
        assert client.get(f"/api/v1/analytics{path}").status_code == 401, path