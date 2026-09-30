"""Normalize provider PostgreSQL URLs for SQLAlchemy's asyncpg driver."""

from __future__ import annotations

from sqlalchemy.engine import make_url


_POSTGRES_DRIVERS = {
    "postgres",
    "postgresql",
    "postgresql+asyncpg",
    "postgresql+psycopg",
    "postgresql+psycopg2",
}


def normalize_async_database_url(database_url: str) -> str:
    """Convert PostgreSQL URLs and common libpq options for asyncpg.

    Managed PostgreSQL providers often supply ``postgresql://`` URLs with
    ``sslmode`` and ``channel_binding`` query options. SQLAlchemy's asyncpg
    dialect accepts the asyncpg option name ``ssl``; ``channel_binding`` is a
    libpq-only option and is not accepted by asyncpg's keyword API.
    """
    url = make_url(database_url)
    if url.drivername not in _POSTGRES_DRIVERS:
        return database_url

    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode is not None:
        query.setdefault("ssl", sslmode)

    return str(url.set(drivername="postgresql+asyncpg", query=query))
