from pydantic import BaseModel
from typing import Literal, List, Optional


class CreateRequest(BaseModel):
    user_id: str
    kind: Literal["access", "group"]
    target_id: int


class RequestOut(BaseModel):
    id: int
    user_id: str
    kind: str
    target_id: int
    status: str
    reason: Optional[str] = None


class PatchStatus(BaseModel):
    status: Literal["approved", "rejected", "pending"]
    reason: Optional[str] = None
