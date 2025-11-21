import os
from typing import AsyncGenerator
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from .db import async_session_factory
from . import schemas
from . import repositories as repo
from . import messaging

ACCESS_SERVICE_URL = os.getenv("ACCESS_SERVICE_URL", "http://localhost:8001")

app = FastAPI(
    title="Request Service",
    version="1.0.0",
    description=(
        "BFF/API Gateway: хранит заявки на доступ/группу, "
        "проксирует запросы в Access, публикует события в очередь."
    ),
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость FastAPI: выдаёт асинхронную сессию БД на время запроса."""
    async with async_session_factory() as session:
        yield session


@app.post(
    "/requests",
    response_model=schemas.RequestOut,
    tags=["Заявки"],
    summary="Создать заявку",
    description=(
        "Создаёт заявку со статусом 'pending' и публикует событие "
        "в очередь для асинхронной проверки/применения."
    ),
)
async def create_request(
    body: schemas.CreateRequest, session: AsyncSession = Depends(get_session)
):
    """
    Создать заявку на доступ или группу для пользователя.
    Статус изначально 'pending'. Также публикует событие
    в очередь для асинхронной авторизации.
    """
    req = await repo.create_request(
        session,
        body.user_id,
        body.kind,
        body.target_id,
    )
    # publish to queue for async authorization
    await messaging.publish_request(
        {
            "request_id": req.id,
            "user_id": body.user_id,
            "kind": body.kind,
            "target_id": body.target_id,
        }
    )
    return schemas.RequestOut.model_validate(req.__dict__)


@app.get(
    "/requests/{request_id}",
    response_model=schemas.RequestOut,
    tags=["Заявки"],
    summary="Получить заявку",
    description=("Возвращает текущий статус и данные заявки по её идентификатору."),
)
async def get_request(
    request_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Получить заявку по идентификатору."""
    req = await repo.get_request(session, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return schemas.RequestOut.model_validate(req.__dict__)


@app.get(
    "/requests/user/{user_id}",
    tags=["Заявки"],
    summary="Все заявки пользователя",
    description=("Возвращает список всех заявок пользователя (по убыванию id)."),
)
async def get_user_requests(
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Получить список всех заявок пользователя."""
    items = await repo.get_user_requests(session, user_id)
    return [schemas.RequestOut.model_validate(i.__dict__) for i in items]


@app.get(
    "/user/{user_id}/rights",
    tags=["Права пользователя"],
    summary="Права пользователя (прокси в Access)",
    description=("Возвращает права пользователя, проксируя запрос в Access Service."),
)
async def proxy_user_rights(user_id: str):
    """Проксирование запроса прав пользователя в Access Service."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{ACCESS_SERVICE_URL}/user/{user_id}/rights")
        return r.json()


@app.post(
    "/user/{user_id}/revoke",
    tags=["Права пользователя"],
    summary="Отозвать право/группу (прокси в Access)",
    description=("Проксирует отзыв доступа/группы в Access Service."),
)
async def proxy_revoke(user_id: str, body: schemas.CreateRequest):
    """Проксирование отзыва доступа/группы в Access Service."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{ACCESS_SERVICE_URL}/user/{user_id}/revoke",
            json={"kind": body.kind, "target_id": body.target_id},
        )
        return r.json()


@app.get(
    "/resource/{resource_id}/access",
    tags=["Ресурсы"],
    summary="Требуемые доступы ресурса (прокси)",
    description=("Возвращает требуемые доступы для ресурса через Access Service."),
)
async def proxy_resource_access(resource_id: int):
    """
    Проксирование запроса требований к доступам
    для ресурса в Access Service.
    """
    async with httpx.AsyncClient() as client:
        url = f"{ACCESS_SERVICE_URL}/resource/{resource_id}/access"
        r = await client.get(url)
        return r.json()


@app.patch(
    "/requests/{request_id}/status",
    response_model=schemas.RequestOut,
    tags=["Заявки"],
    summary="Обновить статус заявки (коллбек)",
    description=(
        "Коллбек от Authorization Service: "
        "устанавливает 'approved' или 'rejected' "
        "для заявки и, при необходимости, причину."
    ),
)
async def patch_status(
    request_id: int,
    body: schemas.PatchStatus,
    session: AsyncSession = Depends(get_session),
):
    """
    Коллбек от Authorization Service:
    изменить статус заявки и необязательную причину.
    """
    req = await repo.patch_status(
        session,
        request_id,
        body.status,
        body.reason,
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return schemas.RequestOut.model_validate(req.__dict__)
