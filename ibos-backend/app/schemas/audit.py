from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


class AuditLogOut(BaseModel):
    id: str
    actor_user_id: str
    action: str
    target_type: str
    target_id: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    pagination: PaginationMeta
