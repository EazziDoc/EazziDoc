import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/eazzidoc_test"


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """
    Single session-scoped sync fixture shared across all test modules.
    Lives in conftest.py so it runs exactly once for the whole session.
    Uses asyncio.run() from a plain sync function — never conflicts with
    pytest-asyncio's session event loop.
    """

    async def _setup():
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _teardown():
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


@pytest.fixture
async def client():
    """
    Fresh engine + session per test. All DB calls within one test share
    one event loop so asyncpg Futures never cross loops.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()
