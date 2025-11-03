from typing import List, Tuple, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from .models import (
    Access,
    RightGroup,
    GroupAccess,
    UserAccess,
    UserGroup,
    ResourceAccess,
)


async def get_user_groups(session: AsyncSession, user_id: str) -> List[RightGroup]:
    """
    Вернуть список групп пользователя.
    :param session: асинхронная сессия БД
    :param user_id: идентификатор пользователя (строка)
    :return: список объектов RightGroup
    """
    stmt = (
        select(RightGroup)
        .join(UserGroup, UserGroup.group_id == RightGroup.id)
        .where(UserGroup.user_id == user_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_direct_accesses(session: AsyncSession, user_id: str) -> List[Access]:
    """
    Вернуть список прямых доступов пользователя (не через группы).
    """
    stmt = (
        select(Access)
        .join(UserAccess, UserAccess.access_id == Access.id)
        .where(UserAccess.user_id == user_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_accesses_for_groups(
    session: AsyncSession, group_ids: List[int]
) -> List[Access]:
    """
    Вернуть доступы, агрегированные всеми группами из списка.
    :param group_ids: список идентификаторов групп
    :return: список объектов Access
    """
    if not group_ids:
        return []
    stmt = (
        select(Access)
        .join(GroupAccess, GroupAccess.access_id == Access.id)
        .where(GroupAccess.group_id.in_(group_ids))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def revoke_user_target(
    session: AsyncSession, user_id: str, kind: str, target_id: int
) -> Tuple[int, int]:
    """
    Отозвать у пользователя доступ или группу.
    :param kind: 'access' или 'group'
    :param target_id: id доступа/группы
    :return: (количество удалённых записей, target_id)
    """
    if kind == "access":
        stmt = delete(UserAccess).where(
            UserAccess.user_id == user_id, UserAccess.access_id == target_id
        )
    else:
        stmt = delete(UserGroup).where(
            UserGroup.user_id == user_id, UserGroup.group_id == target_id
        )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0, target_id


async def get_required_accesses_for_resource(
    session: AsyncSession, resource_id: int
) -> List[Access]:
    """
    Вернуть список доступов, требуемых указанным ресурсом.
    """
    stmt = (
        select(Access)
        .join(ResourceAccess, ResourceAccess.access_id == Access.id)
        .where(ResourceAccess.resource_id == resource_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def apply_access(
    session: AsyncSession, user_id: str, kind: str, target_id: int
) -> None:
    """
    Применить к пользователю доступ или группу (идемпотентно).
    При повторном применении дубликаты игнорируются на уровне БД (ON CONFLICT DO NOTHING).
    """
    if kind == "access":
        stmt = (
            insert(UserAccess)
            .values(user_id=user_id, access_id=target_id)
            .on_conflict_do_nothing(
                index_elements=[UserAccess.user_id, UserAccess.access_id]
            )
        )
    else:
        stmt = (
            insert(UserGroup)
            .values(user_id=user_id, group_id=target_id)
            .on_conflict_do_nothing(
                index_elements=[UserGroup.user_id, UserGroup.group_id]
            )
        )
    await session.execute(stmt)
    await session.commit()


async def get_group_by_id(session: AsyncSession, group_id: int) -> Optional[RightGroup]:
    """
    Вернуть группу по идентификатору или None.
    """
    result = await session.execute(select(RightGroup).where(RightGroup.id == group_id))
    return result.scalar_one_or_none()
