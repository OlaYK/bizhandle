import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess
from app.models.audit_log import AuditLog
from app.models.business_membership import BusinessMembership
from app.models.user import User
from app.schemas.audit import AuditLogListOut, AuditLogOut
from app.schemas.common import PaginationMeta
from app.services.audit_service import (
    build_audit_metadata_preview,
    build_audit_summary,
    build_audit_target_label,
    sanitize_audit_metadata,
)
from app.services.pdf_export_service import build_text_pdf

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _audit_query(
    *,
    business_id: str,
    actor_user_id: str | None,
    action: str | None,
    start_date: date | None,
    end_date: date | None,
):
    count_stmt = select(func.count(AuditLog.id)).where(AuditLog.business_id == business_id)
    data_stmt = (
        select(
            AuditLog,
            User.full_name,
            User.username,
            User.email,
            BusinessMembership.role,
        )
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .outerjoin(
            BusinessMembership,
            (BusinessMembership.user_id == AuditLog.actor_user_id)
            & (BusinessMembership.business_id == AuditLog.business_id),
        )
        .where(AuditLog.business_id == business_id)
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
    return count_stmt, data_stmt


def _audit_log_out(
    *,
    log_row: AuditLog,
    actor_name: str | None,
    actor_username: str | None,
    actor_email: str | None,
    actor_role: str | None,
) -> AuditLogOut:
    sanitized_metadata = sanitize_audit_metadata(log_row.metadata_json)
    return AuditLogOut(
        id=log_row.id,
        actor_user_id=log_row.actor_user_id,
        actor_name=actor_name,
        actor_username=actor_username,
        actor_role=(actor_role or "").lower() or None,
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
        metadata_json=sanitized_metadata,
        metadata_preview=build_audit_metadata_preview(sanitized_metadata),
        created_at=log_row.created_at,
    )


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

    count_stmt, data_stmt = _audit_query(
        business_id=access.business.id,
        actor_user_id=actor_user_id,
        action=action,
        start_date=start_date,
        end_date=end_date,
    )

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        data_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = [
        _audit_log_out(
            log_row=log_row,
            actor_name=actor_name,
            actor_username=actor_username,
            actor_email=actor_email,
            actor_role=actor_role,
        )
        for log_row, actor_name, actor_username, actor_email, actor_role in rows
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


@router.get(
    "/export",
    summary="Export audit logs as CSV or PDF",
    responses={**error_responses(400, 401, 403, 422, 500)},
)
def export_audit_logs(
    format: str = Query(default="csv"),
    actor_user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=5000),
    offset: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    normalized_format = format.strip().lower()
    if normalized_format not in {"csv", "pdf"}:
        raise HTTPException(status_code=400, detail="format must be csv or pdf")

    _, data_stmt = _audit_query(
        business_id=access.business.id,
        actor_user_id=actor_user_id,
        action=action,
        start_date=start_date,
        end_date=end_date,
    )
    data_stmt = data_stmt.order_by(AuditLog.created_at.desc())
    if offset is not None:
        data_stmt = data_stmt.offset(offset)
    if limit is not None:
        data_stmt = data_stmt.limit(limit)

    rows = db.execute(data_stmt).all()
    items = [
        _audit_log_out(
            log_row=log_row,
            actor_name=actor_name,
            actor_username=actor_username,
            actor_email=actor_email,
            actor_role=actor_role,
        )
        for log_row, actor_name, actor_username, actor_email, actor_role in rows
    ]

    if normalized_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "created_at",
                "action",
                "summary",
                "target_label",
                "actor_username",
                "actor_name",
                "actor_role",
                "actor_email",
            ]
        )
        for item in items:
            writer.writerow(
                [
                    item.created_at.isoformat(),
                    item.action,
                    item.summary,
                    item.target_label or "",
                    item.actor_username or "",
                    item.actor_name or "",
                    item.actor_role or "",
                    item.actor_email or "",
                ]
            )
        filename = "audit-logs.csv"
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    lines = [
        f"{item.created_at.isoformat()} | {item.summary} | actor={item.actor_username or item.actor_name or 'unknown'} | role={item.actor_role or '-'}"
        for item in items[:40]
    ]
    pdf_bytes = build_text_pdf(
        title="MoniDesk Audit Export",
        lines=lines,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.pdf"'},
    )
