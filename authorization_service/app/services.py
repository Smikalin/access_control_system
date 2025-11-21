from typing import Iterable, Protocol
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .repositories import has_conflict as repo_has_conflict
from .deps import get_session


class GroupConflictPolicy(Protocol):
    async def has_conflict(self, group_codes: Iterable[str]) -> bool: ...


class RepositoryGroupConflictPolicy:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def has_conflict(self, group_codes: Iterable[str]) -> bool:
        return await repo_has_conflict(self._session, group_codes)


async def get_conflict_policy(
    session: AsyncSession = Depends(get_session),
) -> GroupConflictPolicy:
    return RepositoryGroupConflictPolicy(session)
