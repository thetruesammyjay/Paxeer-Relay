"""Alembic migration environment (async).

Reads the database URL from the ``DATABASE_URL`` environment variable and runs
migrations through an async engine using ``connection.run_sync`` — the standard
pattern for SQLAlchemy 2.x async engines.
"""

from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

# Import the metadata and ALL models so target_metadata is complete for
# autogenerate and so metadata.create_all covers every table.
from paxrelay_db.base import Base
import paxrelay_db  # noqa: F401  (imports every model via the package __init__)

config = context.config

# Inject the runtime database URL. Alembic runs synchronously under the hood,
# but our engine is async, so we keep the asyncpg driver here.
_database_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay",
)
config.set_main_option("sqlalchemy.url", _database_url)

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
