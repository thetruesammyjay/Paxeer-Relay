"""Alembic migration environment (async).

Reads the database URL from the ``DATABASE_URL`` environment variable and runs
migrations through an async engine using ``connection.run_sync`` — the standard
pattern for SQLAlchemy 2.x async engines.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import the metadata and ALL models so target_metadata is complete for
# autogenerate and so metadata.create_all covers every table.
from paxrelay_db.base import Base
from paxrelay_db.urls import normalize_async_database_url
import paxrelay_db  # noqa: F401  (imports every model via the package __init__)

config = context.config

# Show migration progress and the current database revision. The canonical
# package config includes logging sections; the root and API entry-point
# configs intentionally stay small and use standard INFO logging.
if config.config_file_name and config.get_section("loggers"):
    fileConfig(config.config_file_name)
else:
    logging.basicConfig(level=logging.INFO)


def _load_database_url() -> str:
    """Read DATABASE_URL from the shell or the current folder's .env.

    The root .env is a fallback, so Alembic can be run from the repository,
    apps/api, or packages/db without a separate --env-file argument.
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    repository_root = Path(__file__).resolve().parents[5]
    candidates = (Path.cwd() / ".env", repository_root / ".env")
    for env_path in candidates:
        if not env_path.is_file():
            continue
        database_url = dotenv_values(env_path).get("DATABASE_URL")
        if database_url:
            os.environ["DATABASE_URL"] = database_url
            return database_url

    raise RuntimeError(
        "DATABASE_URL is not set. Set it in the current folder's .env or in "
        "the repository root .env before running Alembic."
    )

# Inject the runtime database URL. Alembic runs synchronously under the hood,
# but our engine is async, so we keep the asyncpg driver here.
_database_url = normalize_async_database_url(_load_database_url())
# Alembic's ConfigParser interpolates percent signs; double them so URL-encoded
# credentials (common in managed PostgreSQL connection strings) reach asyncpg.
config.set_main_option("sqlalchemy.url", _database_url.replace("%", "%%"))

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
