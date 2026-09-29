from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Dialect-specific engine setup. SQLite and Supabase/Postgres need different
# handling, and getting this wrong fails at connection time rather than import
# time, so it is kept in one obvious place.


def _normalise_url(url: str) -> str:
    """
    Supabase hands out a connection string beginning `postgresql://`, which
    SQLAlchemy maps to the psycopg2 driver. This project uses psycopg 3, so a
    bare postgres:// scheme is rewritten to the explicit `+psycopg` dialect.
    An explicit driver (e.g. `postgresql+psycopg2://`) is left alone.
    """
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


_url = _normalise_url(settings.database_url)
_is_sqlite = settings.database_url.startswith("sqlite")


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
    # Supabase requires TLS. Only add it if the URL doesn't already say so,
    # otherwise the two settings conflict.
    if "sslmode" not in _url:
        kwargs["connect_args"] = {"sslmode": "require"}
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
