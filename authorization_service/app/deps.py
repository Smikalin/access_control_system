from sqlalchemy.ext.asyncio import AsyncSession
from .db import async_session_factory


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
