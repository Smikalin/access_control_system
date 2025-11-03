import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from authorization_service.app.db import Base
from authorization_service.app.models import ConflictingGroup
from authorization_service.app.repositories import has_conflict


@pytest.mark.asyncio
async def test_has_conflict_true():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as s:
        s.add(ConflictingGroup(group_code_a="DEVELOPER", group_code_b="OWNER"))
        await s.commit()

    async with factory() as s:
        assert await has_conflict(s, ["DEVELOPER", "OWNER"]) is True
        assert await has_conflict(s, ["DEVELOPER"]) is False
        assert await has_conflict(s, ["DEVELOPER", "DB_ADMIN"]) is False
