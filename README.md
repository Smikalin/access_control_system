## Access Control System — Система управления доступами (микросервисы)

Три асинхронных сервиса на FastAPI, объединённые через RabbitMQ и отдельные БД Postgres:
- Request Service (BFF/API Gateway) — точка входа, хранит заявки, проксирует в Access, публикует события в очередь
- Access Service — доменные данные (ресурсы, доступы, группы, права пользователей), применение/отзыв
- Authorization Service — проверка конфликтов групп, асинхронный consumer очереди

### 1. Запуск через Docker Compose

Требования:
- Docker / Docker Desktop с поддержкой Compose v2

Команды (из корня репозитория):
```bash
# Полная пересборка, запуск в фоне
docker compose up --build -d

# Просмотр статуса контейнеров
docker compose ps
```
Доступы по умолчанию:
- Request Service: http://localhost:8000 (Swagger: http://localhost:8000/docs)
- Access Service: http://localhost:8001 (Swagger: http://localhost:8001/docs)
- Authorization Service: http://localhost:8002 (Swagger/health: http://localhost:8002/docs)
- RabbitMQ UI: http://localhost:15672 (логин/пароль: guest/guest)

При старте контейнеров автоматически применяются миграции Alembic. Для Postgres используются отдельные экземпляры:
- access_db (порт хоста 5433)
- auth_db (порт хоста 5434)
- request_db (порт хоста 5435)

### 2. Быстрая проверка работоспособности

1) Authorization Service — health:
- Откройте `http://localhost:8002/docs` → `GET /health` → Execute → ожидаемо: `{ "status": "ok" }`

2) Access Service — сиды групп/ресурсов:
- Откройте `http://localhost:8001/docs`
- `GET /group/{group_id}` → попробуйте `1`, `2`, `3` — ожидаемо: коды `DEVELOPER`, `DB_ADMIN`, `OWNER` (зависит от сидов)
- `GET /resource/{resource_id}/access` → попробуйте `1` (db_cluster), `2` (public_api) — увидите требуемые доступы

### 3. End-to-End сценарии через Swagger (/docs)

Все шаги выполняются через UI Swagger у соответствующего сервиса. По умолчанию используем пользователя `u1`.

#### 3.1. Happy-path: выдача группы DEVELOPER (approve)
1) Request Service → `POST /requests`
   - Body (пример):
     ```json
     { "user_id": "u1", "kind": "group", "target_id": 1 }
     ```
     Где `target_id=1` — это `DEVELOPER` (уточните через `GET /group/1` в Access).
   - Ответ: заявка со статусом `pending` и `id` (запомните `id`).
2) Подождите 2–4 секунды (асинхронный consumer Authorization обработает сообщение).
3) Request Service → `GET /requests/{id}` (подставьте `id` из шага 1)
   - Ожидание: `status = approved`.
4) Request Service → `GET /user/{user_id}/rights` (подставьте `u1`)
   - Ожидание: среди `groups[]` появится `DEVELOPER`, в `effective_accesses[]` — доступы этой группы (например, `API_KEY`).

#### 3.2. Конфликт: заявка на OWNER при уже выданном DEVELOPER (reject)
1) Повторите 3.1 (если ещё не делали) и убедитесь, что `DEVELOPER` уже есть у `u1`.
2) Request Service → `POST /requests`
   - Body:
     ```json
     { "user_id": "u1", "kind": "group", "target_id": 3 }
     ```
     Где `target_id=3` — это `OWNER`.
3) Подождите 2–4 секунды.
4) Request Service → `GET /requests/{id}` (id из шага 2)
   - Ожидание: `status = rejected`, `reason = "Conflicting groups"`.

#### 3.3. Отзыв выданной группы/доступа
1) Убедитесь, что у `u1` есть группа `DEVELOPER` (см. 3.1). Если нет — получите через 3.1.
2) Request Service → `POST /user/{user_id}/revoke` (подставьте `u1`)
   - Body:
     ```json
     { "kind": "group", "target_id": 1 }
     ```
   - Ожидание: `{ "removed": 1 }` при успехе.
3) Request Service → `GET /user/{user_id}/rights`
   - Ожидание: группа `DEVELOPER` отсутствует.

#### 3.4. Ресурс и его требования к доступам
1) Request Service → `GET /resource/{resource_id}/access`
   - Пример: `resource_id=1` (db_cluster) → ожидается список требуемых доступов (например, `DB_READ`).
2) Если нужного доступа нет в `effective_accesses` пользователя — сначала получите нужную группу/доступ (через `POST /requests` или прямо `POST /access/apply` во внутреннем Access для отладки).

#### 3.5. Заявка на несуществующую группу (reject)
1) Request Service → `POST /requests`
   - Body:
     ```json
     { "user_id": "u1", "kind": "group", "target_id": 9999 }
     ```
2) Подождите 2–4 секунды и проверьте `GET /requests/{id}`:
   - Ожидание: `status = rejected`, `reason = "Group not found"` (Authorization проверяет наличие группы через Access).

### 4. Технические заметки

- Все три сервиса запускаются асинхронно; Authorization поднимает consumer RabbitMQ на старте.
- Миграции Alembic выполняются при старте контейнера: сервис не начнёт работать без актуальной схемы.
- Сиды (минимальные справочники) добавляются в миграциях (`access_service/alembic/versions/0001_init.py`, `authorization_service/...`).
- Очередь сообщений: `access_requests` (durable), сообщения помечены как persistent.
- Для отладки очереди используйте RabbitMQ UI: http://localhost:15672.

### 5. Частые проблемы и их решение
- `approved`/`rejected` не проставляется:
  - Проверьте логи Authorization Service: `docker compose logs -n 200 authorization_service`
  - Убедитесь, что Request и Access доступны по внутри-сетевым адресам из переменных окружения (`REQUEST_SERVICE_URL`, `ACCESS_SERVICE_URL`).
- `500 Internal Server Error` в Access при обращении к `/group/{id}`:
  - Проверьте, что миграции применились (в логах Access должен быть `Running upgrade -> 0001_init`).
- Ничего не публикуется в очередь:
  - Проверьте доступность RabbitMQ (порт 5672), убедитесь, что контейнер запущен.

### 6. Запуск отдельного сервиса локально (опционально)
Если нужен локальный запуск без Compose (для отладки):
```bash
cd access_service
poetry install --no-root
export DATABASE_URL=postgresql+asyncpg://access_user:access_pass@localhost:5433/access_db
alembic upgrade head
poetry run uvicorn app.main:app --reload --port 8001
```
Аналогично для `authorization_service` и `request_service` (не забудьте задать соответствующие DATABASE_URL и другие env).

---
