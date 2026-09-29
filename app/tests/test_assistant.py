"""
Assistant tests. Ollama is monkeypatched throughout so the suite runs without a
local model server; the degradation path is covered by the fallback test, which
asserts we answer from real data instead of erroring.
"""
from app.api.v1.assistant import _build_financial_summary
from app.utils import ollama
from app.utils.ollama import OllamaError

OVERVIEW = {
    "balance": 1065.0,
    "total_income": 1500.0,
    "total_expense": 435.0,
    "current_month_income": 1500.0,
    "current_month_expense": 435.0,
    "active_alerts": 2,
}


def _row(name, budgeted, spent, pct):
    return {
        "budget_id": f"b-{name}",
        "category_id": f"c-{name}",
        "category_name": name,
        "month": "2026-09",
        "budgeted": budgeted,
        "spent": spent,
        "utilization_pct": pct,
    }


def test_summary_marks_under_budget_as_within():
    """Regression guard: 185 of 200 is UNDER budget (15 remaining), not over."""
    summary = _build_financial_summary(OVERVIEW, [_row("Groceries", 200.0, 185.0, 92.5)])
    line = next(l for l in summary.splitlines() if "Groceries" in l)
    assert "utilization 92.5%" in line
    assert "within budget, 15.0 remaining" in line
    assert "OVER BUDGET" not in line


def test_summary_marks_real_overage():
    summary = _build_financial_summary(OVERVIEW, [_row("Dining", 200.0, 250.0, 125.0)])
    line = next(l for l in summary.splitlines() if "Dining" in l)
    assert "utilization 125.0%" in line
    assert "OVER BUDGET by 50.0" in line
    assert "remaining" not in line


def test_summary_includes_grounded_balance():
    assert "Balance: 1065.0" in _build_financial_summary(OVERVIEW, [])


def test_summary_handles_no_budgets():
    assert "Budgets: none set yet." in _build_financial_summary(OVERVIEW, [])


def test_chat_grounds_model_in_real_user_data(client, auth_headers, monkeypatch):
    """The prompt sent to the local model must carry this user's real numbers."""
    client.post("/api/v1/transactions", json={
        "amount": 1200, "transaction_type": "income", "description": "Paycheck",
        "transaction_date": "2026-09-01T00:00:00"}, headers=auth_headers)

    captured = {}

    def fake_chat(system_prompt, history, message):
        captured["system_prompt"] = system_prompt
        captured["history"] = history
        captured["message"] = message
        return "stubbed reply"

    monkeypatch.setattr(ollama, "chat", fake_chat)

    resp = client.post("/api/v1/assistant/chat", json={
        "message": "what is my balance?",
        "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    }, headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["reply"] == "stubbed reply"
    assert "Balance: 1200" in captured["system_prompt"]
    assert captured["message"] == "what is my balance?"
    assert len(captured["history"]) == 2


def test_chat_caps_history_to_last_ten_turns(client, auth_headers, monkeypatch):
    captured = {}

    def fake_chat(system_prompt, history, message):
        captured["history"] = history
        return "ok"

    monkeypatch.setattr(ollama, "chat", fake_chat)

    history = [{"role": "user", "content": f"q{i}"} for i in range(25)]
    client.post("/api/v1/assistant/chat", json={"message": "newest", "history": history},
                headers=auth_headers)

    # Only the most recent turns are sent, oldest first.
    assert len(captured["history"]) == 10
    assert captured["history"][0]["content"] == "q15"
    assert captured["history"][-1]["content"] == "q24"


def test_chat_falls_back_when_ollama_unreachable(client, auth_headers, monkeypatch):
    """Ollama down must degrade to a rule-based answer, never a 500."""
    def boom(*args, **kwargs):
        raise OllamaError("Could not reach Ollama at http://localhost:11434")

    monkeypatch.setattr(ollama, "chat", boom)

    client.post("/api/v1/transactions", json={
        "amount": 500, "transaction_type": "income", "description": "Paycheck",
        "transaction_date": "2026-09-01T00:00:00"}, headers=auth_headers)

    resp = client.post("/api/v1/assistant/chat",
                       json={"message": "what is my balance?", "history": []},
                       headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()["reply"]
    assert "500" in body       # answered from real data via the rule-based path
    assert "Ollama" in body    # and told the user why it wasn't the model


def test_status_reports_configured_model(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ollama, "is_available", lambda: True)
    monkeypatch.setattr(ollama, "list_models", lambda: ["llama3:latest", "phi3:mini"])

    body = client.get("/api/v1/assistant/status", headers=auth_headers).json()

    assert body["provider"] == "ollama"
    assert body["available"] is True
    assert body["model_installed"] is True
    assert "phi3:mini" in body["available_models"]


def test_status_requires_auth(client):
    assert client.get("/api/v1/assistant/status").status_code == 401