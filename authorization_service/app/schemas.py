from pydantic import BaseModel
from typing import Literal, Optional, List


class IncomingRequest(BaseModel):
    request_id: int
    user_id: str
    kind: Literal["access", "group"]
    target_id: int


class StatusPatch(BaseModel):
    status: Literal["approved", "rejected"]
    reason: Optional[str] = None


class ConflictCheckRequest(BaseModel):
    codes: List[str]


class ConflictCheckResponse(BaseModel):
    conflict: bool
