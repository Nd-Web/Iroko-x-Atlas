"""
services/database.py — SQLAlchemy async engine, session factory, and
FastAPI dependency for Iroko AI.

Also re-exports ``Base`` so that model modules can use a single import::

    from services.database import Base, get_db

NOTE: The project's primary database setup lives in ``models/database.py``
(synchronous SQLAlchemy, used by the existing routes and agents).  This
module provides the **async** counterpart for new code that requires
``async/await`` database access.  Both share the same ``DATABASE_URL``
from ``core.config.settings``.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

# ── Async URL derivation ─────────────────────────────────────────────────────
# SQLAlchemy async requires an async driver.  We auto-convert common sync
# URLs so callers don't need to duplicate configuration.

_raw_url = settings.DATABASE_URL

if _raw_url.startswith("postgresql://") or _raw_url.startswith("postgres://"):
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
        "postgres://", "postgresql+asyncpg://", 1
    )
elif _raw_url.startswith("postgresql+psycopg2://"):
    _async_url = _raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("sqlite:///"):
    _async_url = _raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
else:
    # Already async or unknown — use as-is
    _async_url = _raw_url


# ── Engine & session factory ──────────────────────────────────────────────────

engine = create_async_engine(
    _async_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Shared declarative base for async models."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_db():
    """
    Yield an ``AsyncSession`` and ensure it is closed after the request.

    Usage in a route::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
