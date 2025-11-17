from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import get_settings
from .models.base import Base
from .models import payment, user  # noqa: F401 - ensure models are registered


_settings = get_settings()
_engine = create_async_engine(_settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def session_factory() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def create_db_and_tables() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
