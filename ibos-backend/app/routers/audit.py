from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogListOut, AuditLogOut
from app.schemas.common import PaginationMeta
from app.services.audit_service import (
    build_audit_metadata_preview,
    build_audit_summary,
    build_audit_target_label,
    sanitize_audit_metadata,
)

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get(
    "",
    response_model=AuditLogListOut,
    summary="List audit logs",
    responses={**error_responses(400, 401, 403, 422, 500)},
)
def list_audit_logs(
    actor_user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    count_stmt = select(func.count(AuditLog.id)).where(AuditLog.business_id == access.business.id)
    data_stmt = (
        select(AuditLog, User.full_name, User.email)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.business_id == access.business.id)
    )

    if actor_user_id:
        count_stmt = count_stmt.where(AuditLog.actor_user_id == actor_user_id)
        data_stmt = data_stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action:
        count_stmt = count_stmt.where(AuditLog.action == action)
        data_stmt = data_stmt.where(AuditLog.action == action)
    if start_date:
        count_stmt = count_stmt.where(func.date(AuditLog.created_at) >= start_date)
        data_stmt = data_stmt.where(func.date(AuditLog.created_at) >= start_date)
    if end_date:
        count_stmt = count_stmt.where(func.date(AuditLog.created_at) <= end_date)
        data_stmt = data_stmt.where(func.date(AuditLog.created_at) <= end_date)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        data_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = [
        AuditLogOut(
            id=log_row.id,
            actor_user_id=log_row.actor_user_id,
            actor_name=actor_name,
            actor_email=sanitize_audit_metadata({"email": actor_email}).get("email") if actor_email else None,
            action=log_row.action,
            summary=build_audit_summary(
                action=log_row.action,
                target_type=log_row.target_type,
                target_id=log_row.target_id,
                metadata_json=log_row.metadata_json,
            ),
            target_type=log_row.target_type,
            target_id=log_row.target_id,
            target_label=build_audit_target_label(
                target_type=log_row.target_type,
                target_id=log_row.target_id,
                metadata_json=log_row.metadata_json,
            ),
            metadata_json=sanitize_audit_metadata(log_row.metadata_json),
            metadata_preview=build_audit_metadata_preview(
                sanitize_audit_metadata(log_row.metadata_json)
            ),
            created_at=log_row.created_at,
        )
        for log_row, actor_name, actor_email in rows
    ]
    count = len(items)
    return AuditLogListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )
