"""
Connection-string handling.

These guard two bugs that only appear with a real Supabase URL, and both of
which fail `alembic upgrade head` -- i.e. they break the Render deploy rather
than anything a developer sees locally.
"""
import configparser

from app.db.database import normalise_database_url


def test_bare_postgres_url_selects_psycopg3():
    """A Supabase URI says postgresql://, which SQLAlchemy maps to psycopg2."""
    assert normalise_database_url("postgresql://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"


def test_explicit_driver_is_left_alone():
    assert normalise_database_url("postgresql+psycopg://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert normalise_database_url("postgresql+psycopg2://u:p@h:5432/d") == "postgresql+psycopg2://u:p@h:5432/d"


def test_sqlite_is_untouched():
    assert normalise_database_url("sqlite:///./finance.db") == "sqlite:///./finance.db"


def test_password_with_at_survives_normalisation():
    """The case that motivated the encoding: "@" inside a password."""
    url = "postgresql://postgres:p%40ss@db.example.co:5432/postgres"
    out = normalise_database_url(url)
    assert "p%40ss@" in out
    assert out.startswith("postgresql+psycopg://")
    assert out.endswith("db.example.co:5432/postgres")


def test_percent_in_password_does_not_break_configparser():
    """
    Regression: a percent-encoded password made alembic.ini parsing fail with
    "invalid interpolation syntax", which broke `alembic upgrade head` -- and
    therefore the whole Render deploy, since preDeployCommand runs it.
    """
    raw = "postgresql://postgres:my%40pass@db.example.co:5432/postgres?sslmode=require"

    # What the unescaped code did: raise before a single migration ran.
    parser = configparser.ConfigParser()
    parser.add_section("alembic")
    try:
        parser.set("alembic", "sqlalchemy.url", raw)
        raised = False
    except ValueError:
        raised = True
    assert raised, "expected configparser to reject an unescaped % in the URL"

    # What the fixed code does: escape it on write, and get it back on read.
    parser.set("alembic", "sqlalchemy.url", normalise_database_url(raw).replace("%", "%%"))
    assert parser.get("alembic", "sqlalchemy.url") == normalise_database_url(raw)