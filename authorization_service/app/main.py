import asyncio
from fastapi import FastAPI
from .consumer import run_consumer

app = FastAPI(
    title="Authorization Service",
    version="1.0.0",
    description=(
        "Сервис проверки конфликтов групп прав. Получает сообщения из очереди,"
        "проверяет правила конфликтов и вызывает Request/Access для обновления состояния."
    ),
)


@app.on_event("startup")
async def startup_event():
    # Fire-and-forget consumer task
    asyncio.create_task(run_consumer())


@app.get("/health", tags=["Техническое"], summary="Проверка здоровья")
async def health():
    """Возвращает статус готовности сервиса к обработке запросов."""
    return {"status": "ok"}
