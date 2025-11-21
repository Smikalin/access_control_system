import asyncio
from fastapi import FastAPI, Depends
from .consumer import run_consumer
from . import schemas
from .services import GroupConflictPolicy, get_conflict_policy

app = FastAPI(
    title="Authorization Service",
    version="1.0.0",
    description=(
        "Сервис проверки конфликтов групп прав. Получает сообщения из очереди,"
        "проверяет правила конфликтов и вызывает "
        "Request/Access для обновления состояния."
    ),
)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_consumer())


@app.get("/health", tags=["Техническое"], summary="Проверка здоровья")
async def health():
    """Возвращает статус готовности сервиса к обработке запросов."""
    return {"status": "ok"}


@app.post(
    "/conflicts/check",
    tags=["Бизнес-правила"],
    summary="Проверить конфликт групп",
    description=(
        "Проверяет наличие конфликта среди переданных кодов групп. "
        "Реализация инкапсулирована в политике, "
        "поставляемой через Depends (инверсия зависимостей)."
    ),
)
async def conflicts_check(
    body: schemas.ConflictCheckRequest,
    policy: GroupConflictPolicy = Depends(get_conflict_policy),
):
    conflict = await policy.has_conflict(body.codes)
    return schemas.ConflictCheckResponse(conflict=conflict)
