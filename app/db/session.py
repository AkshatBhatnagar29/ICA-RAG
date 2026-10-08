from collections.abc import AsyncIterator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


class ResourceManager:
    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    from app.main import resources

    async with resources.session_factory() as session:
        yield session
