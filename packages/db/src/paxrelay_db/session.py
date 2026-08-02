"""Async SQLAlchemy session factory and database dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Module-level engine and session factory — initialised by configure_database()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_database(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    echo: bool = False,
) -> None:
    """Initialise the async engine and session factory.

    Must be called once at application startup (e.g. in the FastAPI lifespan).
    The database_url must use the asyncpg driver:
        postgresql+asyncpg://user:pass@host/dbname
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
        pool_pre_ping=True,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError(
            "Database engine has not been configured. "
            "Call configure_database() before accessing the engine."
        )
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request.

    Usage:
        async def my_route(db: AsyncSession = Depends(get_session)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError(
            "Session factory has not been configured. "
            "Call configure_database() before requesting sessions."
        )
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_database() -> None:
    """Dispose the engine connection pool. Call on application shutdown."""
    if _engine is not None:
        await _engine.dispose()
