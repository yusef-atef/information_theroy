"""
database.py — Async SQLAlchemy Engine Setup

Uses aiosqlite for development (zero config).
Switch DATABASE_URL to postgresql+asyncpg://... for production.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./securecorrect.db"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,   # set True to log all SQL statements
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables. Called during application startup."""
    async with engine.begin() as conn:
        from backend import models  # noqa: F401 — ensure models are imported
        await conn.run_sync(Base.metadata.create_all)
