from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app.*` importable and pull in the real DB URL + models.
from app.core.config import settings
from app.db import base  # noqa: F401  registers all models on Base.metadata
from app.db.database import Base, normalise_database_url

config = context.config

# Two things must happen to the URL before Alembic stores it in the ini file.

# 1. Normalise the scheme. A Supabase URI starts with `postgresql://`, which
#    SQLAlchemy maps to the psycopg2 driver -- this project uses psycopg 3, and
#    without this `alembic upgrade head` dies with "No module named psycopg2".
#    engine_from_config below reads straight from the ini, so it would not get
#    the fix that app/db/database.py applies to the app's own engine.
#
# 2. Escape "%". configparser treats it as the start of an interpolation
#    expression, so a password whose "@" is percent-encoded as "%40" raises
#    "invalid interpolation syntax" before any migration runs. Doubling it is
#    the escape; configparser converts "%%" back to "%" on read.
#
# Both matter at deploy time: Render's preDeployCommand runs `alembic upgrade
# head`, so either one failing fails the whole deployment.
_config_url = normalise_database_url(settings.database_url).replace("%", "%%")
config.set_main_option("sqlalchemy.url", _config_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This was `None` in the original scaffold, which silently disabled
# `alembic revision --autogenerate` (it would always produce an empty
# migration). Pointing it at Base.metadata is what makes autogenerate work.
target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
