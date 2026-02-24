from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogListOut, AuditLogOut
from app.schemas.common import PaginationMeta

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
    data_stmt = select(AuditLog).where(AuditLog.business_id == access.business.id)

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
    ).scalars().all()

    items = [
        AuditLogOut(
            id=row.id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            metadata_json=row.metadata_json,
            created_at=row.created_at,
        )
        for row in rows
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
