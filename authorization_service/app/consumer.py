import asyncio
import json
import httpx
import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from .db import async_session_factory
from .services import RepositoryGroupConflictPolicy
from .settings import settings

REQUEST_SERVICE_URL = settings.request_service_url
ACCESS_SERVICE_URL = settings.access_service_url
RABBITMQ_URL = settings.rabbitmq_url
QUEUE_NAME = settings.requests_queue


async def process_message(message: AbstractIncomingMessage) -> None:
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
        base_request_url = f"{REQUEST_SERVICE_URL}/requests/{request_id}"
        request_status_url = f"{base_request_url}/status"

        async with async_session_factory() as session, httpx.AsyncClient() as client:
            rights_url = f"{ACCESS_SERVICE_URL}/user/{user_id}/rights"
            rights_resp = await client.get(rights_url, timeout=10)
            rights_resp.raise_for_status()
            groups = rights_resp.json().get("groups", [])
            current_group_codes = [g["code"] for g in groups]

            target_group_code = None
            if kind == "group":
                group_url = f"{ACCESS_SERVICE_URL}/group/{target_id}"
                try:
                    g_resp = await client.get(group_url, timeout=10)
                    g_resp.raise_for_status()
                    target_group_code = g_resp.json().get("code")
                except httpx.HTTPStatusError:
                    await client.patch(
                        request_status_url,
                        json={
                            "status": "rejected",
                            "reason": "Group not found",
                        },
                    )
                    return

            candidate_groups = list(current_group_codes)
            if kind == "group" and target_group_code:
                candidate_groups.append(target_group_code)

            policy = RepositoryGroupConflictPolicy(session)
            conflict = await policy.has_conflict(candidate_groups)
            if conflict:
                await client.patch(
                    request_status_url,
                    json={
                        "status": "rejected",
                        "reason": "Conflicting groups",
                    },
                )
                return

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
                request_status_url,
                json={"status": "approved"},
            )


async def run_consumer() -> None:
    """
    Запустить подписчика на очередь RabbitMQ
    и обрабатывать сообщения бесконечно.
    Используется QoS prefetch и подтверждения сообщений.
    """
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.consume(process_message)

    await asyncio.Event().wait()
