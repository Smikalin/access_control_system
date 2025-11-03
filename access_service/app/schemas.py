from pydantic import BaseModel
from typing import List, Literal


class AccessOut(BaseModel):
    """Краткое представление доступа (id и код)."""

    id: int
    code: str


class GroupOut(BaseModel):
    """Краткое представление группы (id и код)."""

    id: int
    code: str


class UserRightsResponse(BaseModel):
    """
    Права пользователя:
    - user_id: идентификатор пользователя
    - groups: список групп
    - direct_accesses: список прямых доступов
    - effective_accesses: объединённые доступы (через группы + прямые)
    """

    user_id: str
    groups: List[GroupOut]
    direct_accesses: List[AccessOut]
    effective_accesses: List[AccessOut]


class RevokeRequest(BaseModel):
    """Запрос на отзыв доступа или группы: kind='access'|'group', target_id — id цели."""

    kind: Literal["access", "group"]
    target_id: int


class ApplyAccessRequest(BaseModel):
    """
    Запрос на применение доступа/группы после одобрения заявки.
    request_id включён для трассируемости, сервис Access его не использует.
    """

    request_id: int
    user_id: str
    kind: Literal["access", "group"]
    target_id: int


class ResourceAccessResponse(BaseModel):
    """Ответ с перечнем требуемых доступов для ресурса."""

    resource_id: int
    required_accesses: List[AccessOut]
