from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import PaginationMeta


class AuditLogOut(BaseModel):
    id: str
    actor_user_id: str
    actor_name: str | None = None
    actor_username: str | None = None
    actor_role: str | None = None
    actor_email: str | None = None
    action: str
    summary: str
    target_type: str
    target_id: str | None = None
    target_label: str | None = None
    metadata_json: dict[str, Any] | None = None
    metadata_preview: list[str] = Field(default_factory=list)
    created_at: datetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    pagination: PaginationMeta
