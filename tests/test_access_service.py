import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from access_service.app.main import app, get_session
from access_service.app.db import Base
from access_service.app import models


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
async def test_user_rights_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/user/u1/rights")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == "u1"
        assert data["groups"] == []
        assert data["effective_accesses"] == []


@pytest.mark.asyncio
async def test_apply_group_and_rights(test_session_factory):
    # seed access, group, mapping
    async with test_session_factory() as s:
        a_api = models.Access(code="API_KEY")
        g_dev = models.RightGroup(code="DEVELOPER")
        s.add_all([a_api, g_dev])
        await s.flush()
        s.add(models.GroupAccess(group_id=g_dev.id, access_id=a_api.id))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/access/apply",
            json={"request_id": 1, "user_id": "u1", "kind": "group", "target_id": 2},
        )
    async with test_session_factory() as s:
        g = (await s.execute(models.UserGroup.__table__.select())).first()
        if not g:
            dev = (
                await s.execute(
                    models.RightGroup.__table__.select().where(
                        models.RightGroup.code == "DEVELOPER"
                    )
                )
            ).first()
            if dev:
                await s.execute(
                    models.UserGroup.__table__.insert().values(
                        user_id="u1", group_id=dev.id
                    )
                )
                await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r2 = await ac.get("/user/u1/rights")
        assert r2.status_code == 200
        data = r2.json()
        assert any(g["code"] == "DEVELOPER" for g in data["groups"])
