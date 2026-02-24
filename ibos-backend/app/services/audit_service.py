import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit_event(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        id=str(uuid.uuid4()),
        business_id=business_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata_json,
    )
    db.add(event)
    return event
