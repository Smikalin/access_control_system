from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .models import Request


async def create_request(
    session: AsyncSession, user_id: str, kind: str, target_id: int
) -> Request:
    """
    Создать заявку со статусом 'pending'.
    Возвращает созданную запись Request.
    """
    req = Request(user_id=user_id, kind=kind, target_id=target_id, status="pending")
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req


async def get_request(session: AsyncSession, request_id: int) -> Optional[Request]:
    """Вернуть заявку по идентификатору или None."""
    res = await session.execute(select(Request).where(Request.id == request_id))
    return res.scalar_one_or_none()


async def get_user_requests(session: AsyncSession, user_id: str) -> List[Request]:
    """Вернуть все заявки пользователя (по убыванию id)."""
    res = await session.execute(
        select(Request).where(Request.user_id == user_id).order_by(Request.id.desc())
    )
    return list(res.scalars().all())


async def patch_status(
    session: AsyncSession, request_id: int, status: str, reason: Optional[str]
) -> Optional[Request]:
    """
    Изменить статус заявки и при необходимости указать причину.
    Возвращает обновлённую заявку или None, если не найдена.
    """
    res = await session.execute(select(Request).where(Request.id == request_id))
    req = res.scalar_one_or_none()
    if not req:
        return None
    req.status = status
    req.reason = reason
    await session.commit()
    await session.refresh(req)
    return req
