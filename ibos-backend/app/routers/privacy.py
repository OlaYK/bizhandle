import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import to_money
from app.core.permissions import RBAC_V2_PERMISSION_MATRIX, require_business_roles, require_permission
from app.core.security_current import BusinessAccess, get_current_user
from app.models.audit_log import AuditLog, AuditLogArchive
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.privacy_document import CustomerDocument
from app.models.user import User
from app.schemas.privacy import (
    AuditArchiveOut,
    CustomerDocumentCreateIn,
    CustomerDocumentListOut,
    CustomerDocumentOut,
    CustomerDocumentPublicOut,
    CustomerDocumentSignIn,
    CustomerPiiDeleteOut,
    CustomerPiiDocumentOut,
    CustomerPiiExportOut,
    CustomerPiiInvoiceOut,
    CustomerPiiOrderOut,
    PermissionMatrixOut,
    RolePermissionOut,
)
from app.services.audit_service import log_audit_event
from app.services.display_service import build_display_reference
from app.services.pdf_export_service import build_text_pdf

router = APIRouter(prefix="/privacy", tags=["privacy"])

ALLOWED_CUSTOMER_DOCUMENT_STATUSES = {
    "pending_signature",
    "signed",
    "revoked",
    "expired",
}


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
    documents: list[CustomerDocument],
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
                reference=build_display_reference("ORD", row.id),
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
                reference=build_display_reference("INV", row.id),
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
        documents=[
            CustomerPiiDocumentOut(
                id=row.id,
                document_type=row.document_type,
                title=row.title,
                status=row.status,
                file_url=row.file_url,
                signed_at=row.signed_at,
                created_at=row.created_at,
            )
            for row in documents
        ],
    )


def _sync_customer_document_status(document: CustomerDocument) -> None:
    expires_at = document.sign_token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        document.status == "pending_signature"
        and expires_at
        and expires_at <= datetime.now(timezone.utc)
    ):
        document.status = "expired"


def _customer_document_or_404(
    db: Session,
    *,
    business_id: str,
    document_id: str,
) -> CustomerDocument:
    row = db.execute(
        select(CustomerDocument).where(
            CustomerDocument.id == document_id,
            CustomerDocument.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Customer document not found")
    _sync_customer_document_status(row)
    return row


def _customer_document_by_token_or_404(db: Session, *, sign_token: str) -> CustomerDocument:
    row = db.execute(
        select(CustomerDocument).where(CustomerDocument.sign_token == sign_token)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Customer document not found")
    _sync_customer_document_status(row)
    return row


def _customer_document_out(
    document: CustomerDocument,
    *,
    customer_name: str | None = None,
) -> CustomerDocumentOut:
    share_url = f"/privacy/customer-documents/sign/{document.sign_token}" if document.sign_token else None
    return CustomerDocumentOut(
        id=document.id,
        customer_id=document.customer_id,
        customer_name=customer_name,
        order_id=document.order_id,
        order_reference=build_display_reference("ORD", document.order_id),
        invoice_id=document.invoice_id,
        invoice_reference=build_display_reference("INV", document.invoice_id),
        document_type=document.document_type,
        title=document.title,
        status=document.status,
        file_url=document.file_url,
        consent_text=document.consent_text,
        recipient_name=document.recipient_name,
        recipient_email=document.recipient_email,
        recipient_phone=document.recipient_phone,
        share_url=share_url,
        sign_token_expires_at=document.sign_token_expires_at,
        signed_by_name=document.signed_by_name,
        signed_at=document.signed_at,
        signer_ip=document.signer_ip,
        metadata_json=document.metadata_json,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _customer_document_public_out(document: CustomerDocument) -> CustomerDocumentPublicOut:
    return CustomerDocumentPublicOut(
        title=document.title,
        document_type=document.document_type,
        status=document.status,
        file_url=document.file_url,
        consent_text=document.consent_text,
        recipient_name=document.recipient_name,
        sign_token_expires_at=document.sign_token_expires_at,
        signed_by_name=document.signed_by_name,
        signed_at=document.signed_at,
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
    documents = db.execute(
        select(CustomerDocument).where(
            CustomerDocument.business_id == access.business.id,
            CustomerDocument.customer_id == customer.id,
        )
    ).scalars().all()

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="privacy.customer.export",
        target_type="customer",
        target_id=customer.id,
        metadata_json={
            "orders_count": len(orders),
            "invoices_count": len(invoices),
            "documents_count": len(documents),
            "customer_name": customer.name,
        },
    )
    db.commit()

    return _build_customer_pii_export(
        customer=customer,
        orders=orders,
        invoices=invoices,
        documents=documents,
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
        f"Documents Count: {len(payload.documents)}",
        "",
        "Recent Orders:",
    ]

    for order in payload.orders[:10]:
        lines.append(
            f"- {order.reference or order.id} | {order.status} | {order.channel} | {order.total_amount:.2f}"
        )

    lines.append("")
    lines.append("Recent Invoices:")
    for invoice in payload.invoices[:10]:
        lines.append(
            f"- {invoice.reference or invoice.id} | {invoice.status} | {invoice.currency} | "
            f"{invoice.total_amount:.2f} (paid {invoice.amount_paid:.2f})"
        )

    lines.append("")
    lines.append("Customer Documents:")
    for document in payload.documents[:10]:
        lines.append(
            f"- {document.id[:8]}... | {document.document_type} | {document.status} | {document.title}"
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
    "/customer-documents",
    response_model=CustomerDocumentOut,
    summary="Create customer document for consent/signature capture",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_customer_document(
    payload: CustomerDocumentCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=payload.customer_id)
    if payload.order_id:
        order = db.execute(
            select(Order).where(
                Order.id == payload.order_id,
                Order.business_id == access.business.id,
            )
        ).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
    if payload.invoice_id:
        invoice = db.execute(
            select(Invoice).where(
                Invoice.id == payload.invoice_id,
                Invoice.business_id == access.business.id,
            )
        ).scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

    if not payload.file_url and not payload.consent_text:
        raise HTTPException(status_code=400, detail="Provide file_url or consent_text")

    recipient_name = payload.recipient_name or customer.name
    recipient_email = payload.recipient_email or customer.email
    recipient_phone = payload.recipient_phone or customer.phone
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(int(payload.expires_in_days), 1))
    document = CustomerDocument(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        customer_id=customer.id,
        order_id=payload.order_id,
        invoice_id=payload.invoice_id,
        created_by_user_id=actor.id,
        document_type=payload.document_type.strip(),
        title=payload.title.strip(),
        status="pending_signature",
        file_url=payload.file_url,
        consent_text=payload.consent_text,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
        sign_token=uuid.uuid4().hex,
        sign_token_expires_at=expires_at,
        metadata_json=payload.metadata_json,
    )
    db.add(document)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="privacy.customer_document.create",
        target_type="customer_document",
        target_id=document.id,
        metadata_json={
            "customer_id": customer.id,
            "customer_name": customer.name,
            "document_type": document.document_type,
            "title": document.title,
            "recipient_email": recipient_email,
            "recipient_phone": recipient_phone,
        },
    )
    db.commit()
    db.refresh(document)
    return _customer_document_out(document, customer_name=customer.name)


@router.get(
    "/customer-documents",
    response_model=CustomerDocumentListOut,
    summary="List customer documents",
    responses=error_responses(400, 401, 403, 422, 500),
)
def list_customer_documents(
    customer_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    normalized_status = status.strip().lower() if status and status.strip() else None
    if normalized_status and normalized_status not in ALLOWED_CUSTOMER_DOCUMENT_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_CUSTOMER_DOCUMENT_STATUSES))
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {allowed}")

    stmt = (
        select(CustomerDocument, Customer.name)
        .join(Customer, Customer.id == CustomerDocument.customer_id)
        .where(CustomerDocument.business_id == access.business.id)
    )
    if customer_id:
        stmt = stmt.where(CustomerDocument.customer_id == customer_id)
    if normalized_status:
        stmt = stmt.where(CustomerDocument.status == normalized_status)
    if document_type and document_type.strip():
        stmt = stmt.where(CustomerDocument.document_type == document_type.strip())

    rows = db.execute(stmt.order_by(CustomerDocument.created_at.desc())).all()
    items = []
    changed = False
    for document, customer_name in rows:
        previous_status = document.status
        _sync_customer_document_status(document)
        changed = changed or previous_status != document.status
        items.append(_customer_document_out(document, customer_name=customer_name))
    if changed:
        db.commit()
    return CustomerDocumentListOut(items=items)


@router.get(
    "/customer-documents/{document_id}",
    response_model=CustomerDocumentOut,
    summary="Get customer document detail",
    responses=error_responses(401, 403, 404, 500),
)
def get_customer_document(
    document_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    document = _customer_document_or_404(
        db,
        business_id=access.business.id,
        document_id=document_id,
    )
    customer = _customer_or_404(db, business_id=access.business.id, customer_id=document.customer_id)
    db.commit()
    return _customer_document_out(document, customer_name=customer.name)


@router.get(
    "/customer-documents/sign/{sign_token}",
    response_model=CustomerDocumentPublicOut,
    summary="Get public customer document signing view",
    responses=error_responses(404, 410, 500),
)
def get_customer_document_public(sign_token: str, db: Session = Depends(get_db)):
    document = _customer_document_by_token_or_404(db, sign_token=sign_token)
    if document.status == "revoked":
        raise HTTPException(status_code=410, detail="Customer document has been revoked")
    if document.status == "expired":
        db.commit()
        raise HTTPException(status_code=410, detail="Customer document has expired")
    if document.status == "signed":
        return _customer_document_public_out(document)
    db.commit()
    return _customer_document_public_out(document)


@router.post(
    "/customer-documents/sign/{sign_token}",
    response_model=CustomerDocumentPublicOut,
    summary="Sign customer document",
    responses=error_responses(400, 404, 410, 422, 500),
)
def sign_customer_document(
    sign_token: str,
    payload: CustomerDocumentSignIn,
    request: Request,
    db: Session = Depends(get_db),
):
    document = _customer_document_by_token_or_404(db, sign_token=sign_token)
    if not payload.accepted:
        raise HTTPException(status_code=400, detail="accepted must be true to sign the document")
    if document.status == "revoked":
        raise HTTPException(status_code=410, detail="Customer document has been revoked")
    if document.status == "expired":
        db.commit()
        raise HTTPException(status_code=410, detail="Customer document has expired")
    if document.status == "signed":
        return _customer_document_public_out(document)

    document.status = "signed"
    document.signed_by_name = payload.signer_name or document.recipient_name
    document.signature_note = payload.note
    document.signed_at = datetime.now(timezone.utc)
    document.signer_ip = request.client.host if request.client else None

    log_audit_event(
        db,
        business_id=document.business_id,
        actor_user_id=document.created_by_user_id,
        action="privacy.customer_document.sign",
        target_type="customer_document",
        target_id=document.id,
        metadata_json={
            "document_type": document.document_type,
            "title": document.title,
            "signed_by_name": document.signed_by_name,
        },
    )
    db.commit()
    db.refresh(document)
    return _customer_document_public_out(document)


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
