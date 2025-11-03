import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from request_service.app.main import app, get_session
from request_service.app.db import Base


@pytest.fixture(scope="module")
async def test_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield factory


@pytest.fixture(autouse=True)
async def override_session(test_session_factory):
    async def _get_session():
        async with test_session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _get_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_and_patch_request(monkeypatch):
    # avoid actual RabbitMQ publish
    async def dummy_publish(_: dict) -> None:
        return None

    from request_service.app import messaging

    monkeypatch.setattr(messaging, "publish_request", dummy_publish)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/requests", json={"user_id": "u1", "kind": "group", "target_id": 1}
        )
        assert r.status_code == 200
        rid = r.json()["id"]

        p = await ac.patch(f"/requests/{rid}/status", json={"status": "approved"})
        assert p.status_code == 200
        assert p.json()["status"] == "approved"
