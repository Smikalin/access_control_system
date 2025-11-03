from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Text, DateTime
from datetime import datetime, timezone
from typing import Optional
from .db import Base


class Request(Base):
    """
    Модель заявки на выдачу прав.
    Поля:
    - user_id: пользователь, для которого создаётся заявка
    - kind: тип ('access' или 'group')
    - target_id: целевой id доступа или группы
    - status: статус обработки ('pending'|'approved'|'rejected')
    - reason: причина отказа (если есть)
    - created_at / updated_at: отметки времени
    """

    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # 'access' | 'group'
    target_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
