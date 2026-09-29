import uuid

from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func


def gen_uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    """Adds created_at / updated_at columns backed by the database's own clock.

    (The original models used Django's `auto_now_add`/`auto_now`, which don't
    exist in SQLAlchemy and would raise a TypeError on import. `server_default`
    / `onupdate` with `func.now()` are the SQLAlchemy equivalents.)
    """

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
