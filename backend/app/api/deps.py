"""FastAPI dependency injection — shared resources for route handlers."""

from collections.abc import AsyncGenerator
from typing import Annotated

import anthropic
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Database engine — created once at startup
_engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


DbSession = Annotated[AsyncSession, Depends(get_db)]
AnthropicClient = Annotated[anthropic.AsyncAnthropic, Depends(get_anthropic_client)]
