from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Dialect-specific engine setup. SQLite and Supabase/Postgres need different
# handling, and getting this wrong fails at connection time rather than import
# time, so it is kept in one obvious place.


def normalise_database_url(url: str) -> str:
    """
    Supabase hands out a connection string beginning `postgresql://`, which
    SQLAlchemy maps to the psycopg2 driver. This project uses psycopg 3, so a
    bare postgres:// scheme is rewritten to the explicit `+psycopg` dialect.
    An explicit driver (e.g. `postgresql+psycopg2://`) is left alone.

    Exported so the test suite creates its engine the same way the app does.
    """
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


# Backwards-compatible private alias.
_normalise_url = normalise_database_url

_url = normalise_database_url(settings.database_url)
_is_sqlite = settings.database_url.startswith("sqlite")


def _is_pgbouncer(url: str) -> bool:
    """
    True for Supabase's pooler host, which is PgBouncer. Port 6543 is the
    transaction-mode pooler; 5432 on that host is the session pooler, which
    keeps one backend for the life of the connection and is safe.
    """
    return "pooler.supabase.com" in url and ":6543" in url


def _engine_kwargs() -> dict:
    if _is_sqlite:
        # SQLite needs this connect arg when used from multiple threads
        # (as FastAPI does).
        return {"connect_args": {"check_same_thread": False}}

    kwargs: dict = {
        # Supabase's pooler (and most hosted Postgres) close idle connections
        # after a while. pool_pre_ping detects a dead connection and opens a
        # fresh one instead of handing the caller a broken socket.
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        # Recycle before the server's idle timeout kills a pooled connection.
        "pool_recycle": settings.db_pool_recycle_seconds,
    }

    connect_args: dict = {}
    if "sslmode" not in _url:
        connect_args["sslmode"] = "require"

    # Supabase's connection pooler is PgBouncer in *transaction* mode, which
    # hands a different backend connection to each client transaction. psycopg 3
    # prepares statements server-side after a query runs a few times
    # (prepare_threshold defaults to 5); a prepared statement belongs to the
    # backend that created it, so reusing one that PgBouncer has since swapped
    # out fails intermittently -- and only in production, under real traffic.
    # Disabling server-side preparation costs a negligible amount of parsing
    # and removes the whole failure mode.
    if _is_pgbouncer(_url):
        connect_args["prepare_threshold"] = None

    if connect_args:
        kwargs["connect_args"] = connect_args
    return kwargs


engine = create_engine(_url, **_engine_kwargs())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a request-scoped DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
