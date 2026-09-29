import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.v1 import alerts, analytics, assistant, auth, budgets, categories, transactions
from app.core.config import settings
from app.db import base  # noqa: F401  (registers all models on Base.metadata)
from app.db.database import Base, engine
from app.api.health import database_url_looks_like_placeholder

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if database_url_looks_like_placeholder():
        logger.warning(
            "DATABASE_URL still contains .env.example placeholder values. Every "
            "database request will fail until you paste your real Supabase "
            "connection string into .env (Dashboard > Project Settings > Database "
            "> Connection string)."
        )
    # Convenience for local dev / SQLite. Against a real database (Supabase)
    # set DB_AUTO_CREATE_TABLES=false and run `alembic upgrade head` instead:
    # create_all only ever creates missing tables, so it would silently ignore
    # column and constraint changes on an existing schema.
    if settings.db_auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Personal Finance Management API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)  # GET /health, unauthenticated
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(categories.router, prefix="/api/v1", tags=["categories"])
app.include_router(transactions.router, prefix="/api/v1", tags=["transactions"])
app.include_router(budgets.router, prefix="/api/v1", tags=["budgets"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(assistant.router, prefix="/api/v1/assistant", tags=["assistant"])


@app.get("/")
async def root():
    return {"message": "Welcome to the Personal Finance Management API"}
