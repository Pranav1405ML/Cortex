"""
Alembic env.py — THE MIGRATION ENGINE

This file tells Alembic:
  1. Where to find your database (DATABASE_URL from .env)
  2. What your models look like (Base.metadata)
  3. How to connect (async, because we use asyncpg)
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Load .env so DATABASE_URL is available to Settings
from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.db.base import Base

# CRITICAL: This import looks unused, but it's not!
# It forces Python to execute models/__init__.py, which imports
# User, Conversation, Message — registering them on Base.metadata.
# Without this, Alembic would see an empty database and generate nothing.
import app.models  # noqa: F401

config = context.config

# Feed the DATABASE_URL from .env into Alembic's config
# We replace % with %% because Alembic's INI parser treats % as special
# (it uses % for variable interpolation like %(here)s in the .ini file).
config.set_main_option(
    "sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%")
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic compares against the live database.
# It looks at Base.metadata (which knows about all our models)
# and says "what tables/columns exist in code but not in the DB?"
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to the DB. Rarely used."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Helper that runs inside a sync context."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect to the DB with an async engine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point — kicks off the async migration."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
