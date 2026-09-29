"""Liveness / readiness probe. Unauthenticated on purpose -- orchestrators and
load balancers call this without credentials."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

# Markers left in the .env.example template. If one of these survives into a
# real deployment, every query fails with a DNS error, so say so loudly at
# startup rather than letting it surface as a confusing 500 later.
_PLACEHOLDER_MARKERS = ("PROJECT-REF", "YOUR-PASSWORD", "YOUR_DB_PASSWORD", "aws-0-REGION")


def database_url_looks_like_placeholder() -> bool:
    return any(marker in settings.database_url for marker in _PLACEHOLDER_MARKERS)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Returns 200 when the app is up. `database` reports whether it can
    actually reach Postgres, so a failed deploy is obvious immediately."""
    try:
        db.execute(text("SELECT 1"))
        database = {"connected": True}
    except Exception as exc:
        # Deliberately not fatal: /health still answers 200 so the app is
        # reported as "running but misconfigured" rather than "down".
        database = {"connected": False, "error": exc.__class__.__name__}

    warnings: list[str] = []
    if settings.secret_key == "dev-secret-key-change-me":
        warnings.append(
            "SECRET_KEY is still the development default. Anyone can forge a valid "
            "JWT with it, so set a real secret before exposing this to anyone."
        )
    if settings.cors_origins.strip() == "*":
        warnings.append(
            "CORS_ORIGINS is '*', which lets any site call this API from a "
            "browser. Restrict it to your real frontend origin."
        )

    return {
        "status": "ok" if database["connected"] and not warnings else "degraded",
        "database": database,
        "warnings": warnings,
    }