import asyncio
import os
from collections.abc import AsyncGenerator
from fnmatch import fnmatchcase

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use SQLite for tests before app modules initialize their default engine.
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production"

from app.api.deps import get_redis
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class InMemoryRedis:
    """Minimal Redis test double that persists for one test."""

    def __init__(self):
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if self.data.pop(key, None) is not None:
                deleted += 1
        return deleted

    async def delete_pattern(self, pattern: str) -> int:
        keys = [key for key in self.data if fnmatchcase(key, pattern)]
        return await self.delete(*keys)

    async def exists(self, key: str) -> bool:
        return key in self.data


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def redis_client() -> InMemoryRedis:
    return InMemoryRedis()


@pytest.fixture
async def client(redis_client: InMemoryRedis) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_redis] = lambda: redis_client
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session


@pytest.fixture
def auth_headers() -> dict:
    """Create auth headers with a valid token for testing."""
    token = create_access_token(data={"sub": "00000000-0000-0000-0000-000000000001"})
    return {"Authorization": f"Bearer {token}"}
