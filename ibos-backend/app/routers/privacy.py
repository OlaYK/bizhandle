import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import to_money
from app.core.permissions import RBAC_V2_PERMISSION_MATRIX, require_permission
from app.core.security_current import BusinessAccess, get_current_user
from app.models.audit_log import AuditLog, AuditLogArchive
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.user import User
from app.schemas.privacy import (
    AuditArchiveOut,
    CustomerPiiDeleteOut,
    CustomerPiiExportOut,
    CustomerPiiInvoiceOut,
    CustomerPiiOrderOut,
    PermissionMatrixOut,
    RolePermissionOut,
)
from app.services.audit_service import log_audit_event
from app.services.pdf_export_service import build_text_pdf

router = APIRouter(prefix="/privacy", tags=["privacy"])


def _customer_or_404(db: Session, *, business_id: str, customer_id: str) -> Customer:
    customer = db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _build_customer_pii_export(
    *,
    customer: Customer,
    orders: list[Order],
    invoices: list[Invoice],
) -> CustomerPiiExportOut:
    return CustomerPiiExportOut(
        customer_id=customer.id,
        exported_at=datetime.now(timezone.utc),
        customer={
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "note": customer.note,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
            "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
        },
        orders=[
            CustomerPiiOrderOut(
                id=row.id,
                status=row.status,
                channel=row.channel,
                total_amount=float(to_money(row.total_amount)),
                created_at=row.created_at,
            )
            for row in orders
        ],
        invoices=[
            CustomerPiiInvoiceOut(
                id=row.id,
                status=row.status,
                currency=row.currency,
                total_amount=float(to_money(row.total_amount)),
                amount_paid=float(to_money(row.amount_paid)),
                issue_date=datetime.combine(row.issue_date, time.min, tzinfo=timezone.utc)
                if row.issue_date
                else None,
                created_at=row.created_at,
            )
            for row in invoices
        ],
    )


@router.get(
    "/rbac/matrix",
    response_model=PermissionMatrixOut,
    summary="Get RBAC v2 role-permission matrix",
    responses=error_responses(401, 403, 500),
)
def get_rbac_matrix(
    access: BusinessAccess = Depends(require_permission("analytics.view")),
):
    _ = access
    items = [
        RolePermissionOut(role=role, permissions=sorted(list(permissions)))
        for role, permissions in RBAC_V2_PERMISSION_MATRIX.items()
    ]
    items.sort(key=lambda row: row.role)
    return PermissionMatrixOut(items=items)


@router.get(
    "/customers/{customer_id}/export",
    response_model=CustomerPiiExportOut,
    summary="Export customer PII and linked records",
    responses=error_responses(401, 403, 404, 500),
)
def export_customer_pii(
    customer_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("privacy.customer.export")),
    actor: User = Depends(get_current_user),
):
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=customer_id)

    orders = db.execute(
        select(Order).where(
            Order.business_id == access.business.id,
            Order.customer_id == customer.id,
        )
    ).scalars().all()
    invoices = db.execute(
        select(Invoice).where(
            Invoice.business_id == access.business.id,
            Invoice.customer_id == customer.id,
        )
    ).scalars().all()

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="privacy.customer.export",
        target_type="customer",
        target_id=customer.id,
        metadata_json={"orders_count": len(orders), "invoices_count": len(invoices)},
    )
    db.commit()

    return _build_customer_pii_export(
        customer=customer,
        orders=orders,
        invoices=invoices,
    )


@router.get(
    "/customers/{customer_id}/export/download",
    summary="Download customer PII export as PDF",
    responses=error_responses(401, 403, 404, 500),
)
def download_customer_pii_export_pdf(
    customer_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("privacy.customer.export")),
    actor: User = Depends(get_current_user),
):
    payload = export_customer_pii(
        customer_id=customer_id,
        db=db,
        access=access,
        actor=actor,
    )

    customer_data = payload.customer or {}
    lines = [
        f"Customer ID: {payload.customer_id}",
        f"Name: {customer_data.get('name') or '-'}",
        f"Email: {customer_data.get('email') or '-'}",
        f"Phone: {customer_data.get('phone') or '-'}",
        f"Orders Count: {len(payload.orders)}",
        f"Invoices Count: {len(payload.invoices)}",
        "",
        "Recent Orders:",
    ]

    for order in payload.orders[:10]:
        lines.append(
            f"- {order.id[:8]}... | {order.status} | {order.channel} | {order.total_amount:.2f}"
        )

    lines.append("")
    lines.append("Recent Invoices:")
    for invoice in payload.invoices[:10]:
        lines.append(
            f"- {invoice.id[:8]}... | {invoice.status} | {invoice.currency} | "
            f"{invoice.total_amount:.2f} (paid {invoice.amount_paid:.2f})"
        )

    pdf_bytes = build_text_pdf(
        title="MoniDesk Customer PII Export",
        lines=lines,
        generated_at=payload.exported_at,
    )
    filename = f"customer-pii-export-{payload.customer_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/customers/{customer_id}",
    response_model=CustomerPiiDeleteOut,
    summary="Delete customer PII (anonymize)",
    responses=error_responses(401, 403, 404, 500),
)
def delete_customer_pii(
    customer_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("privacy.customer.delete")),
    actor: User = Depends(get_current_user),
):
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=customer_id)
    customer.name = f"Deleted Customer {customer.id[:6]}"
    customer.phone = None
    customer.email = None
    customer.note = "PII deleted by admin workflow"

    deleted_fields = ["phone", "email", "note"]
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="privacy.customer.delete",
        target_type="customer",
        target_id=customer.id,
        metadata_json={"deleted_fields": deleted_fields},
    )
    db.commit()
    return CustomerPiiDeleteOut(
        customer_id=customer.id,
        anonymized=True,
        deleted_fields=deleted_fields,
        processed_at=datetime.now(timezone.utc),
    )


@router.post(
    "/audit-archive",
    response_model=AuditArchiveOut,
    summary="Archive and optionally delete historical audit logs",
    responses=error_responses(400, 401, 403, 500),
)
def archive_audit_logs(
    cutoff_date: date = Query(...),
    delete_archived: bool = Query(default=True),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("privacy.audit.archive")),
    actor: User = Depends(get_current_user),
):
    cutoff_dt = datetime.combine(cutoff_date, time.max, tzinfo=timezone.utc)
    rows = db.execute(
        select(AuditLog).where(
            AuditLog.business_id == access.business.id,
            AuditLog.created_at <= cutoff_dt,
        )
    ).scalars().all()
    payload = [
        {
            "id": row.id,
            "actor_user_id": row.actor_user_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "metadata_json": row.metadata_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    archive = AuditLogArchive(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        archived_by_user_id=actor.id,
        cutoff_date=cutoff_dt,
        records_count=len(payload),
        payload_json=payload,
    )
    db.add(archive)

    if delete_archived and rows:
        row_ids = [row.id for row in rows]
        db.execute(
            delete(AuditLog).where(
                AuditLog.business_id == access.business.id,
                AuditLog.id.in_(row_ids),
            )
        )

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="privacy.audit.archive",
        target_type="audit_log_archive",
        target_id=archive.id,
        metadata_json={
            "cutoff_date": cutoff_date.isoformat(),
            "records_count": len(payload),
            "delete_archived": delete_archived,
        },
    )
    db.commit()
    return AuditArchiveOut(
        archive_id=archive.id,
        cutoff_date=cutoff_dt,
        records_count=len(payload),
        archived_at=archive.created_at,
    )
