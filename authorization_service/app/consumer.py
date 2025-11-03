import os
import asyncio
import json
import httpx
import aio_pika
from sqlalchemy.ext.asyncio import AsyncSession
from .db import async_session_factory
from .repositories import has_conflict

REQUEST_SERVICE_URL = os.getenv("REQUEST_SERVICE_URL", "http://localhost:8000")
ACCESS_SERVICE_URL = os.getenv("ACCESS_SERVICE_URL", "http://localhost:8001")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
QUEUE_NAME = os.getenv("REQUESTS_QUEUE", "access_requests")


async def process_message(message: aio_pika.IncomingMessage) -> None:
    """
    Обработать одно сообщение из очереди:
    1) распарсить payload {request_id, user_id, kind, target_id}
    2) получить текущие права пользователя из Access
    3) при kind=group — получить код целевой группы; если не найдена — reject
    4) проверить конфликт; при наличии — PATCH rejected в Request
       иначе — POST /access/apply, затем PATCH approved в Request
    """
    async with message.process():
        payload = json.loads(message.body)
        request_id = payload["request_id"]
        user_id = payload["user_id"]
        kind = payload["kind"]
        target_id = payload["target_id"]

        async with async_session_factory() as session:
            async with httpx.AsyncClient() as client:
                rights_resp = await client.get(
                    f"{ACCESS_SERVICE_URL}/user/{user_id}/rights", timeout=10
                )
                rights_resp.raise_for_status()
                rights = rights_resp.json()
                current_group_codes = [g["code"] for g in rights.get("groups", [])]
                target_group_code = None
                if kind == "group":
                    try:
                        g_resp = await client.get(
                            f"{ACCESS_SERVICE_URL}/group/{target_id}", timeout=10
                        )
                        g_resp.raise_for_status()
                        target_group_code = g_resp.json().get("code")
                    except httpx.HTTPStatusError:
                        await client.patch(
                            f"{REQUEST_SERVICE_URL}/requests/{request_id}/status",
                            json={"status": "rejected", "reason": "Group not found"},
                        )
                        return

            candidate_groups = list(current_group_codes)
            if kind == "group" and target_group_code:
                candidate_groups.append(target_group_code)

            conflict = await has_conflict(session, candidate_groups)

            async with httpx.AsyncClient() as client:
                if conflict:
                    await client.patch(
                        f"{REQUEST_SERVICE_URL}/requests/{request_id}/status",
                        json={"status": "rejected", "reason": "Conflicting groups"},
                    )
                else:
                    await client.post(
                        f"{ACCESS_SERVICE_URL}/access/apply",
                        json={
                            "request_id": request_id,
                            "user_id": user_id,
                            "kind": kind,
                            "target_id": target_id,
                        },
                    )
                    await client.patch(
                        f"{REQUEST_SERVICE_URL}/requests/{request_id}/status",
                        json={"status": "approved"},
                    )


async def run_consumer() -> None:
    """
    Запустить подписчика на очередь RabbitMQ и обрабатывать сообщения бесконечно.
    Используется QoS prefetch и подтверждения сообщений.
    """
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.consume(process_message)

    await asyncio.Event().wait()
