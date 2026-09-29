from app.api.health import database_url_looks_like_placeholder


def test_health_reports_connected_database(client):
    """The suite overrides the DB with a working one, so this is the happy path."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True


def test_health_needs_no_auth(client):
    """Orchestrators call /health without credentials, so it must not 401."""
    assert client.get("/health").status_code == 200


def test_placeholder_detection(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "database_url",
        "postgresql://postgres.PROJECT-REF:YOUR-PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres",
    )
    assert database_url_looks_like_placeholder() is True

    monkeypatch.setattr(
        settings, "database_url",
        "postgresql://postgres.abcdefg:realpass@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require",
    )
    assert database_url_looks_like_placeholder() is False

    monkeypatch.setattr(settings, "database_url", "sqlite:///./finance.db")
    assert database_url_looks_like_placeholder() is False