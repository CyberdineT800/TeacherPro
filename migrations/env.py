"""Alembic environment — async SQLAlchemy with asyncpg.

Usage:
    # Auto-generate a migration from model changes:
    alembic revision --autogenerate -m "describe change"

    # Apply all pending migrations:
    alembic upgrade head

    # Downgrade one step:
    alembic downgrade -1

NOTE: The existing init_db() in models.py still runs on startup and handles
      ADD COLUMN IF NOT EXISTS guards for older deployments.  Alembic is the
      preferred path for all future schema changes.
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

# Load .env so DATABASE_URL is available
load_dotenv()

# Import the shared Base so Alembic can detect model changes
from models import Base  # noqa: E402

# Alembic Config object — gives access to alembic.ini values
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Pick up the real DATABASE_URL from the environment
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://teacherpro:teacherpro@localhost:5432/teacherpro",
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL script, no DB connection)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to the real database)."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
