import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .db import async_session_factory
from . import schemas
from . import models
from . import repositories as repo

app = FastAPI(
    title="Access Service",
    version="1.0.0",
    description=(
        "Сервис управления доменными данными: ресурсы, доступы, группы прав и права пользователей.\n\n"
        "Предоставляет внутренние API для чтения прав, требований ресурсов, применения и отзыва прав."
    ),
)


async def get_session() -> AsyncSession:
    """Зависимость FastAPI: выдаёт асинхронную сессию БД на время запроса."""
    async with async_session_factory() as session:
        yield session


@app.get(
    "/user/{user_id}/rights",
    response_model=schemas.UserRightsResponse,
    tags=["Права пользователя"],
    summary="Получить права пользователя",
    description=(
        "Возвращает группы пользователя, прямые доступы и эффективные доступы (объединение без дубликатов)."
    ),
)
async def get_user_rights(user_id: str, session: AsyncSession = Depends(get_session)):
    """
    Получить права пользователя:
    - группы (`groups`)
    - прямые доступы (`direct_accesses`)
    - эффективные доступы (`effective_accesses`) — объединение без дубликатов
    """
    groups = await repo.get_user_groups(session, user_id)
    direct_accesses = await repo.get_user_direct_accesses(session, user_id)
    group_accesses = await repo.get_accesses_for_groups(session, [g.id for g in groups])

    def to_access_out(a: models.Access) -> schemas.AccessOut:
        return schemas.AccessOut(id=a.id, code=a.code)

    def to_group_out(g: models.RightGroup) -> schemas.GroupOut:
        return schemas.GroupOut(id=g.id, code=g.code)

    eff_map = {a.id: a for a in direct_accesses}
    for a in group_accesses:
        eff_map.setdefault(a.id, a)

    return schemas.UserRightsResponse(
        user_id=user_id,
        groups=[to_group_out(g) for g in groups],
        direct_accesses=[to_access_out(a) for a in direct_accesses],
        effective_accesses=[to_access_out(a) for a in eff_map.values()],
    )


@app.post(
    "/user/{user_id}/revoke",
    tags=["Права пользователя"],
    summary="Отозвать право/группу у пользователя",
    description=(
        "Удаляет привязку доступа или группы от пользователя. Идемпотентно: при отсутствии записи вернёт removed=0."
    ),
)
async def revoke(
    user_id: str,
    body: schemas.RevokeRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Отозвать у пользователя доступ или группу.
    Тело: { kind: 'access' | 'group', target_id: int }
    Возвращает количество удалённых записей.
    """
    deleted, _ = await repo.revoke_user_target(
        session, user_id, body.kind, body.target_id
    )
    return {"removed": deleted}


@app.get(
    "/resource/{resource_id}/access",
    response_model=schemas.ResourceAccessResponse,
    tags=["Ресурсы"],
    summary="Требуемые доступы для ресурса",
    description="Возвращает список доступов, необходимых для доступа к ресурсу.",
)
async def resource_access(
    resource_id: int, session: AsyncSession = Depends(get_session)
):
    """Вернуть список доступов, требуемых указанным ресурсом."""
    accesses = await repo.get_required_accesses_for_resource(session, resource_id)
    if accesses is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return schemas.ResourceAccessResponse(
        resource_id=resource_id,
        required_accesses=[schemas.AccessOut(id=a.id, code=a.code) for a in accesses],
    )


@app.post(
    "/access/apply",
    tags=["Применение прав"],
    summary="Применить доступ/группу к пользователю",
    description=(
        "Применяет доступ или группу к пользователю после одобрения заявки.\n"
        "Валидация: проверяется существование целевой записи. Идемпотентно."
    ),
)
async def access_apply(
    body: schemas.ApplyAccessRequest, session: AsyncSession = Depends(get_session)
):
    """
    Применить к пользователю доступ или группу после успешной заявки.
    Валидация: проверяется существование целевого объекта.
    """
    if body.kind == "access":
        exists_stmt = select(models.Access.id).where(models.Access.id == body.target_id)
    else:
        exists_stmt = select(models.RightGroup.id).where(
            models.RightGroup.id == body.target_id
        )
    res = await session.execute(exists_stmt)
    if res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Target not found")

    await repo.apply_access(session, body.user_id, body.kind, body.target_id)
    return {"applied": True}


@app.get(
    "/group/{group_id}",
    tags=["Справочники"],
    summary="Информация о группе",
    description="Служебная ручка для получения кода группы по её идентификатору.",
)
async def get_group(group_id: int, session: AsyncSession = Depends(get_session)):
    """Вернуть краткую информацию о группе (id, code) по её идентификатору."""
    g = await repo.get_group_by_id(session, group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"id": g.id, "code": g.code}
