import csv
import io
import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import ZERO_MONEY, to_money
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceEvent, InvoiceInstallment, InvoicePayment, InvoiceTemplate
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductVariant
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.invoice import (
    ALLOWED_INVOICE_STATUSES,
    ALLOWED_TEMPLATE_STATUSES,
    InvoiceAgingBucketOut,
    InvoiceAgingCustomerOut,
    InvoiceAgingDashboardOut,
    InvoiceCreate,
    InvoiceCreateOut,
    InvoiceFxQuoteOut,
    InvoiceInstallmentListOut,
    InvoiceInstallmentOut,
    InvoiceInstallmentUpsertIn,
    InvoiceListOut,
    InvoiceMarkPaidIn,
    InvoiceOut,
    InvoicePaymentCreateIn,
    InvoicePaymentListOut,
    InvoicePaymentOut,
    InvoiceReminderIn,
    InvoicePreviewLineItemOut,
    InvoicePreviewOut,
    InvoiceReminderPolicyIn,
    InvoiceReminderPolicyOut,
    InvoiceReminderRunOut,
    InvoiceSendIn,
    InvoiceStatementExportOut,
    InvoiceStatementItemOut,
    InvoiceStatementListOut,
    InvoiceTemplateListOut,
    InvoiceTemplateOut,
    InvoiceTemplateUpsertIn,
)
from app.services.audit_service import log_audit_event
from app.services.display_service import get_customer_name_map

router = APIRouter(prefix="/invoices", tags=["invoices"])

FX_RATE_QUANT = Decimal("0.000001")

_USD_PER_CURRENCY = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.08"),
    "GBP": Decimal("1.26"),
    "CAD": Decimal("0.74"),
    "NGN": Decimal("0.00066"),
    "GHS": Decimal("0.065"),
    "KES": Decimal("0.0078"),
    "ZAR": Decimal("0.053"),
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_rate(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(FX_RATE_QUANT, rounding=ROUND_HALF_UP)


def _normalize_currency(value: str) -> str:
    normalized = (value or "").strip().upper()
    if len(normalized) != 3:
        raise HTTPException(status_code=400, detail="currency must be a 3-letter code")
    return normalized


def _lookup_fx_rate(from_currency: str, to_currency: str) -> Decimal:
    from_code = _normalize_currency(from_currency)
    to_code = _normalize_currency(to_currency)
    if from_code == to_code:
        return Decimal("1.000000")
    usd_per_from = _USD_PER_CURRENCY.get(from_code)
    usd_per_to = _USD_PER_CURRENCY.get(to_code)
    if usd_per_from is None or usd_per_to is None:
        return Decimal("1.000000")
    return _to_rate(usd_per_from / usd_per_to)


def _invoice_or_404(db: Session, *, business_id: str, invoice_id: str) -> Invoice:
    row = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.business_id == business_id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return row


def _template_or_404(db: Session, *, business_id: str, template_id: str) -> InvoiceTemplate:
    row = db.execute(
        select(InvoiceTemplate).where(
            InvoiceTemplate.id == template_id,
            InvoiceTemplate.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice template not found")
    return row


def _customer_exists(db: Session, *, business_id: str, customer_id: str) -> bool:
    row = db.execute(
        select(Customer.id).where(Customer.id == customer_id, Customer.business_id == business_id)
    ).scalar_one_or_none()
    return bool(row)


def _customer_for_invoice(
    db: Session,
    *,
    business_id: str,
    customer_id: str | None,
) -> Customer | None:
    if not customer_id:
        return None
    return db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.business_id == business_id)
    ).scalar_one_or_none()


def _default_reminder_policy_dict() -> dict:
    defaults = InvoiceReminderPolicyIn()
    return defaults.model_dump()


def _reminder_policy_for_invoice(invoice: Invoice) -> dict:
    defaults = _default_reminder_policy_dict()
    raw = invoice.reminder_policy_json if isinstance(invoice.reminder_policy_json, dict) else {}
    merged = {**defaults, **raw}
    try:
        return InvoiceReminderPolicyIn.model_validate(merged).model_dump()
    except Exception:
        return defaults


def _to_policy_out(invoice: Invoice) -> InvoiceReminderPolicyOut:
    policy = _reminder_policy_for_invoice(invoice)
    return InvoiceReminderPolicyOut(
        enabled=bool(policy["enabled"]),
        first_delay_days=int(policy["first_delay_days"]),
        cadence_days=int(policy["cadence_days"]),
        max_reminders=int(policy["max_reminders"]),
        escalation_after_days=int(policy["escalation_after_days"]),
        channels=list(policy["channels"]),
        reminder_count=int(invoice.reminder_count or 0),
        escalation_level=int(invoice.escalation_level or 0),
        next_reminder_at=invoice.next_reminder_at,
    )


def _record_invoice_event(
    db: Session,
    *,
    invoice: Invoice,
    event_type: str,
    idempotency_key: str | None = None,
    metadata_json: dict | None = None,
) -> None:
    db.add(
        InvoiceEvent(
            id=str(uuid.uuid4()),
            invoice_id=invoice.id,
            business_id=invoice.business_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            metadata_json=metadata_json,
        )
    )


def _invoice_template_out(template: InvoiceTemplate | None) -> InvoiceTemplateOut | None:
    if template is None:
        return None
    return InvoiceTemplateOut(
        id=template.id,
        name=template.name,
        status=template.status,
        is_default=bool(template.is_default),
        brand_name=template.brand_name,
        logo_url=template.logo_url,
        primary_color=template.primary_color,
        footer_text=template.footer_text,
        config_json=template.config_json,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _outstanding_amount(invoice: Invoice) -> Decimal:
    return to_money(max(to_money(invoice.total_amount) - to_money(invoice.amount_paid), ZERO_MONEY))


def _outstanding_amount_base(invoice: Invoice) -> Decimal:
    return to_money(max(to_money(invoice.total_amount_base) - to_money(invoice.amount_paid_base), ZERO_MONEY))


def _invoice_out(invoice: Invoice, *, customer_name: str | None = None) -> InvoiceOut:
    return InvoiceOut(
        id=invoice.id,
        customer_id=invoice.customer_id,
        customer_name=customer_name,
        order_id=invoice.order_id,
        status=invoice.status,
        currency=invoice.currency,
        base_currency=invoice.base_currency,
        fx_rate_to_base=float(_to_rate(invoice.fx_rate_to_base)),
        total_amount=float(to_money(invoice.total_amount)),
        total_amount_base=float(to_money(invoice.total_amount_base)),
        amount_paid=float(to_money(invoice.amount_paid)),
        amount_paid_base=float(to_money(invoice.amount_paid_base)),
        outstanding_amount=float(_outstanding_amount(invoice)),
        outstanding_amount_base=float(_outstanding_amount_base(invoice)),
        template_id=invoice.template_id,
        payment_reference=invoice.payment_reference,
        payment_method=invoice.payment_method,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        last_sent_at=invoice.last_sent_at,
        paid_at=invoice.paid_at,
        reminder_count=int(invoice.reminder_count or 0),
        escalation_level=int(invoice.escalation_level or 0),
        next_reminder_at=invoice.next_reminder_at,
        note=invoice.note,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def _installment_out(installment: InvoiceInstallment) -> InvoiceInstallmentOut:
    remaining = max(to_money(installment.amount) - to_money(installment.paid_amount), ZERO_MONEY)
    return InvoiceInstallmentOut(
        id=installment.id,
        due_date=installment.due_date,
        amount=float(to_money(installment.amount)),
        paid_amount=float(to_money(installment.paid_amount)),
        remaining_amount=float(to_money(remaining)),
        status=installment.status,
        note=installment.note,
    )


def _payment_out(payment: InvoicePayment) -> InvoicePaymentOut:
    return InvoicePaymentOut(
        id=payment.id,
        invoice_id=payment.invoice_id,
        amount=float(to_money(payment.amount)),
        amount_base=float(to_money(payment.amount_base)),
        currency=payment.currency,
        fx_rate_to_base=float(_to_rate(payment.fx_rate_to_base)),
        payment_method=payment.payment_method,
        payment_reference=payment.payment_reference,
        idempotency_key=payment.idempotency_key,
        note=payment.note,
        paid_at=payment.paid_at,
        created_at=payment.created_at,
    )


def _resolve_invoice_delivery_target(
    *,
    customer: Customer | None,
    channel: str | None,
    recipient_override: str | None,
) -> tuple[str, str | None]:
    normalized_channel = (channel or "manual").strip().lower() or "manual"
    if normalized_channel == "manual":
        return "manual", recipient_override
    if recipient_override:
        return normalized_channel, recipient_override
    if customer is None:
        raise HTTPException(status_code=400, detail="Customer is required for channel-based delivery")
    recipient = customer.email if normalized_channel == "email" else customer.phone
    if not recipient:
        field_name = "email" if normalized_channel == "email" else "phone"
        raise HTTPException(
            status_code=400,
            detail=f"Customer {field_name} is required for {normalized_channel} delivery",
        )
    return normalized_channel, recipient


def _build_invoice_delivery_options(customer: Customer | None) -> tuple[list, str]:
    options = []
    has_email = bool(customer and customer.email)
    has_phone = bool(customer and customer.phone)
    options.append(
        {
            "channel": "manual",
            "recipient": None,
            "ready": True,
            "reason": None,
        }
    )
    options.append(
        {
            "channel": "email",
            "recipient": customer.email if customer else None,
            "ready": has_email,
            "reason": None if has_email else "Customer email missing",
        }
    )
    options.append(
        {
            "channel": "whatsapp",
            "recipient": customer.phone if customer else None,
            "ready": has_phone,
            "reason": None if has_phone else "Customer phone missing",
        }
    )
    options.append(
        {
            "channel": "sms",
            "recipient": customer.phone if customer else None,
            "ready": has_phone,
            "reason": None if has_phone else "Customer phone missing",
        }
    )
    recommended_channel = "email" if has_email else "whatsapp" if has_phone else "manual"
    return options, recommended_channel


def _invoice_preview_line_items(
    db: Session,
    *,
    business_id: str,
    order_id: str | None,
) -> list[InvoicePreviewLineItemOut]:
    if not order_id:
        return []
    rows = db.execute(
        select(
            OrderItem.variant_id,
            Product.id,
            Product.name,
            ProductVariant.size,
            ProductVariant.label,
            ProductVariant.sku,
            OrderItem.qty,
            OrderItem.unit_price,
            OrderItem.line_total,
        )
        .join(ProductVariant, ProductVariant.id == OrderItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            OrderItem.order_id == order_id,
            ProductVariant.business_id == business_id,
        )
        .order_by(Product.name.asc(), ProductVariant.size.asc(), ProductVariant.label.asc())
    ).all()
    return [
        InvoicePreviewLineItemOut(
            variant_id=variant_id,
            product_id=product_id,
            product_name=product_name,
            size=size,
            label=label,
            sku=sku,
            qty=int(qty),
            unit_price=float(to_money(unit_price)),
            line_total=float(to_money(line_total)),
        )
        for variant_id, product_id, product_name, size, label, sku, qty, unit_price, line_total in rows
    ]


def _build_invoice_preview(
    db: Session,
    *,
    business_name: str,
    invoice: Invoice,
) -> InvoicePreviewOut:
    customer = _customer_for_invoice(
        db,
        business_id=invoice.business_id,
        customer_id=invoice.customer_id,
    )
    template = (
        _template_or_404(db, business_id=invoice.business_id, template_id=invoice.template_id)
        if invoice.template_id
        else None
    )
    delivery_options_payload, recommended_channel = _build_invoice_delivery_options(customer)
    line_items = _invoice_preview_line_items(
        db,
        business_id=invoice.business_id,
        order_id=invoice.order_id,
    )
    installments = _installment_list_out(db, invoice=invoice).items
    reminder_policy = _to_policy_out(invoice)
    customer_name = customer.name if customer else None
    display_business_name = template.brand_name if template and template.brand_name else business_name
    amount_due = float(_outstanding_amount(invoice))
    subject = f"Invoice {invoice.id[:8]} from {display_business_name}"
    message_preview = (
        f"Hello {customer_name or 'customer'}, your invoice for "
        f"{invoice.currency} {amount_due:.2f} from {display_business_name} is ready."
    )
    return InvoicePreviewOut(
        invoice=_invoice_out(invoice, customer_name=customer_name),
        customer_name=customer_name,
        customer_email=customer.email if customer else None,
        customer_phone=customer.phone if customer else None,
        template=_invoice_template_out(template),
        delivery_options=[
            {
                **option,
                "suggested": option["channel"] == recommended_channel,
            }
            for option in delivery_options_payload
        ],
        recommended_channel=recommended_channel,
        subject=subject,
        message_preview=message_preview,
        line_items=line_items,
        installments=installments,
        reminder_policy=reminder_policy,
    )


def _send_invoice_now(
    db: Session,
    *,
    invoice: Invoice,
    customer: Customer | None,
    channel: str | None,
    recipient_override: str | None,
    note: str | None,
    event_type: str = "send",
) -> tuple[str, str | None]:
    if invoice.status in {"paid", "cancelled"}:
        raise HTTPException(status_code=400, detail="Cannot send paid/cancelled invoice")

    delivery_channel, recipient = _resolve_invoice_delivery_target(
        customer=customer,
        channel=channel,
        recipient_override=recipient_override,
    )
    now = datetime.now(timezone.utc)
    if invoice.status == "draft":
        invoice.status = "sent"
    invoice.last_sent_at = now
    policy = _reminder_policy_for_invoice(invoice)
    if invoice.next_reminder_at is None:
        invoice.next_reminder_at = _compute_next_reminder_at(
            invoice=invoice,
            policy=policy,
            now=now,
            reset_first=True,
        )
    _record_invoice_event(
        db,
        invoice=invoice,
        event_type=event_type,
        metadata_json={
            "channel": delivery_channel,
            "recipient": recipient,
            "note": note,
            "delivery_status": "sent",
        },
    )
    return delivery_channel, recipient


def _compute_next_reminder_at(
    *,
    invoice: Invoice,
    policy: dict,
    now: datetime,
    reset_first: bool = False,
) -> datetime | None:
    if not policy.get("enabled", False):
        return None
    if invoice.status in {"paid", "cancelled"}:
        return None
    if _outstanding_amount(invoice) <= ZERO_MONEY:
        return None

    if reset_first or int(invoice.reminder_count or 0) == 0:
        anchor_date = invoice.due_date or invoice.issue_date
        return datetime.combine(anchor_date, time.min, tzinfo=timezone.utc) + timedelta(
            days=int(policy["first_delay_days"])
        )
    return now + timedelta(days=int(policy["cadence_days"]))


def _sync_installments_from_paid_amount(db: Session, *, invoice: Invoice) -> None:
    installments = db.execute(
        select(InvoiceInstallment)
        .where(
            InvoiceInstallment.invoice_id == invoice.id,
            InvoiceInstallment.business_id == invoice.business_id,
        )
        .order_by(InvoiceInstallment.due_date.asc(), InvoiceInstallment.created_at.asc())
    ).scalars().all()
    if not installments:
        return

    remaining_paid = to_money(invoice.amount_paid)
    today = date.today()
    for installment in installments:
        installment_amount = to_money(installment.amount)
        applied = ZERO_MONEY
        if remaining_paid > ZERO_MONEY:
            applied = to_money(min(installment_amount, remaining_paid))
            remaining_paid = to_money(max(remaining_paid - applied, ZERO_MONEY))
        installment.paid_amount = applied

        if applied >= installment_amount:
            installment.status = "paid"
        elif applied > ZERO_MONEY:
            installment.status = "partially_paid"
        elif installment.due_date < today:
            installment.status = "overdue"
        else:
            installment.status = "pending"


def _installment_list_out(db: Session, *, invoice: Invoice) -> InvoiceInstallmentListOut:
    rows = db.execute(
        select(InvoiceInstallment)
        .where(
            InvoiceInstallment.invoice_id == invoice.id,
            InvoiceInstallment.business_id == invoice.business_id,
        )
        .order_by(InvoiceInstallment.due_date.asc(), InvoiceInstallment.created_at.asc())
    ).scalars().all()
    total_scheduled = sum((to_money(row.amount) for row in rows), ZERO_MONEY)
    total_paid = sum((to_money(row.paid_amount) for row in rows), ZERO_MONEY)
    total_remaining = max(total_scheduled - total_paid, ZERO_MONEY)
    return InvoiceInstallmentListOut(
        items=[_installment_out(row) for row in rows],
        total_scheduled=float(to_money(total_scheduled)),
        total_paid=float(to_money(total_paid)),
        total_remaining=float(to_money(total_remaining)),
    )


def _ensure_invoice_not_cancelled(invoice: Invoice) -> None:
    if invoice.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cancelled invoice cannot be updated")


def _ensure_invoice_template_belongs_to_business(
    db: Session,
    *,
    business_id: str,
    template_id: str | None,
) -> None:
    if not template_id:
        return
    _template_or_404(db, business_id=business_id, template_id=template_id)


def _auto_mark_overdue_invoices(db: Session, *, business_id: str) -> int:
    today = date.today()
    rows = db.execute(
        select(Invoice).where(
            Invoice.business_id == business_id,
            Invoice.status.in_(["sent", "partially_paid", "overdue"]),
            Invoice.due_date.is_not(None),
            Invoice.due_date < today,
        )
    ).scalars().all()
    changed = 0
    for row in rows:
        if _outstanding_amount(row) > ZERO_MONEY and row.status != "overdue":
            row.status = "overdue"
            changed += 1
    return changed


def _apply_payment(
    db: Session,
    *,
    invoice: Invoice,
    amount: Decimal | None,
    payment_method: str | None,
    payment_reference: str | None,
    idempotency_key: str | None,
    note: str | None,
    paid_at: datetime | None,
    event_type: str,
) -> InvoicePayment:
    _ensure_invoice_not_cancelled(invoice)

    outstanding = _outstanding_amount(invoice)
    if outstanding <= ZERO_MONEY:
        raise HTTPException(status_code=400, detail="Invoice is already fully paid")

    effective_amount = to_money(amount if amount is not None else outstanding)
    if effective_amount <= ZERO_MONEY:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")
    if effective_amount > outstanding:
        raise HTTPException(status_code=400, detail="Payment amount cannot exceed outstanding balance")

    effective_paid_at = _as_utc(paid_at or datetime.now(timezone.utc))
    fx_rate = _to_rate(invoice.fx_rate_to_base)
    amount_base = to_money(effective_amount * fx_rate)

    payment = InvoicePayment(
        id=str(uuid.uuid4()),
        invoice_id=invoice.id,
        business_id=invoice.business_id,
        amount=effective_amount,
        amount_base=amount_base,
        currency=invoice.currency,
        fx_rate_to_base=fx_rate,
        payment_method=payment_method,
        payment_reference=payment_reference,
        idempotency_key=idempotency_key,
        note=note,
        paid_at=effective_paid_at,
    )
    db.add(payment)

    invoice.amount_paid = to_money(to_money(invoice.amount_paid) + effective_amount)
    invoice.amount_paid_base = to_money(to_money(invoice.amount_paid_base) + amount_base)
    if payment_method:
        invoice.payment_method = payment_method
    if payment_reference:
        invoice.payment_reference = payment_reference

    if _outstanding_amount(invoice) <= ZERO_MONEY:
        invoice.status = "paid"
        invoice.paid_at = effective_paid_at
        invoice.next_reminder_at = None
    elif invoice.due_date and invoice.due_date < effective_paid_at.date():
        invoice.status = "overdue"
    else:
        invoice.status = "partially_paid"

    _record_invoice_event(
        db,
        invoice=invoice,
        event_type=event_type,
        idempotency_key=idempotency_key,
        metadata_json={
            "amount": float(effective_amount),
            "amount_base": float(amount_base),
            "payment_method": payment_method,
            "payment_reference": payment_reference,
        },
    )
    _sync_installments_from_paid_amount(db, invoice=invoice)
    return payment


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")


@router.get(
    "/fx-quote",
    response_model=InvoiceFxQuoteOut,
    summary="Get FX quote for invoice conversion",
    responses=error_responses(400, 401, 403, 422, 500),
)
def get_fx_quote(
    from_currency: str = Query(..., min_length=3, max_length=3),
    to_currency: str = Query(..., min_length=3, max_length=3),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _ = access
    from_code = _normalize_currency(from_currency)
    to_code = _normalize_currency(to_currency)
    return InvoiceFxQuoteOut(
        from_currency=from_code,
        to_currency=to_code,
        rate=float(_lookup_fx_rate(from_code, to_code)),
        as_of=datetime.now(timezone.utc),
    )


@router.put(
    "/templates",
    response_model=InvoiceTemplateOut,
    summary="Create or update invoice template",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def upsert_invoice_template(
    payload: InvoiceTemplateUpsertIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    template: InvoiceTemplate | None = None
    if payload.template_id:
        template = _template_or_404(db, business_id=access.business.id, template_id=payload.template_id)

    if payload.is_default:
        existing_defaults = db.execute(
            select(InvoiceTemplate).where(
                InvoiceTemplate.business_id == access.business.id,
                InvoiceTemplate.is_default.is_(True),
            )
        ).scalars().all()
        for row in existing_defaults:
            if not template or row.id != template.id:
                row.is_default = False

    if template is None:
        template = InvoiceTemplate(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            name=payload.name,
            status=payload.status,
            is_default=payload.is_default,
            brand_name=payload.brand_name,
            logo_url=payload.logo_url,
            primary_color=payload.primary_color,
            footer_text=payload.footer_text,
            config_json=payload.config_json,
        )
        db.add(template)
        action = "invoice.template.create"
    else:
        template.name = payload.name
        template.status = payload.status
        template.is_default = payload.is_default
        template.brand_name = payload.brand_name
        template.logo_url = payload.logo_url
        template.primary_color = payload.primary_color
        template.footer_text = payload.footer_text
        template.config_json = payload.config_json
        action = "invoice.template.update"

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action=action,
        target_type="invoice_template",
        target_id=template.id,
        metadata_json={
            "status": template.status,
            "is_default": bool(template.is_default),
        },
    )
    db.commit()
    db.refresh(template)
    return InvoiceTemplateOut(
        id=template.id,
        name=template.name,
        status=template.status,
        is_default=bool(template.is_default),
        brand_name=template.brand_name,
        logo_url=template.logo_url,
        primary_color=template.primary_color,
        footer_text=template.footer_text,
        config_json=template.config_json,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get(
    "/templates",
    response_model=InvoiceTemplateListOut,
    summary="List invoice templates",
    responses=error_responses(400, 401, 403, 422, 500),
)
def list_invoice_templates(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    stmt = select(InvoiceTemplate).where(InvoiceTemplate.business_id == access.business.id)
    if status and status.strip():
        normalized_status = status.strip().lower()
        if normalized_status not in ALLOWED_TEMPLATE_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_TEMPLATE_STATUSES))
            raise HTTPException(status_code=400, detail=f"Invalid template status. Allowed: {allowed}")
        stmt = stmt.where(InvoiceTemplate.status == normalized_status)

    rows = db.execute(
        stmt.order_by(InvoiceTemplate.is_default.desc(), InvoiceTemplate.updated_at.desc())
    ).scalars().all()
    items = [
        InvoiceTemplateOut(
            id=row.id,
            name=row.name,
            status=row.status,
            is_default=bool(row.is_default),
            brand_name=row.brand_name,
            logo_url=row.logo_url,
            primary_color=row.primary_color,
            footer_text=row.footer_text,
            config_json=row.config_json,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    return InvoiceTemplateListOut(items=items)


@router.get(
    "/aging",
    response_model=InvoiceAgingDashboardOut,
    summary="Accounts receivable aging dashboard",
    responses=error_responses(400, 401, 403, 422, 500),
)
def get_aging_dashboard(
    as_of_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    snapshot_date = as_of_date or date.today()
    _auto_mark_overdue_invoices(db, business_id=access.business.id)
    db.flush()

    rows = db.execute(
        select(Invoice).where(
            Invoice.business_id == access.business.id,
            Invoice.status.in_(["draft", "sent", "partially_paid", "overdue"]),
        )
    ).scalars().all()

    bucket_totals: dict[str, Decimal] = {
        "not_due": ZERO_MONEY,
        "1_30": ZERO_MONEY,
        "31_60": ZERO_MONEY,
        "61_90": ZERO_MONEY,
        "91_plus": ZERO_MONEY,
    }
    bucket_counts = {key: 0 for key in bucket_totals.keys()}
    by_currency: dict[str, Decimal] = {}
    customer_totals: dict[str | None, Decimal] = {}

    total_outstanding_base = ZERO_MONEY
    overdue_count = 0
    partially_paid_count = 0
    for row in rows:
        outstanding = _outstanding_amount(row)
        if outstanding <= ZERO_MONEY:
            continue
        outstanding_base = _outstanding_amount_base(row)
        total_outstanding_base += outstanding_base
        if row.status == "partially_paid":
            partially_paid_count += 1

        by_currency[row.currency] = to_money(by_currency.get(row.currency, ZERO_MONEY) + outstanding)
        customer_totals[row.customer_id] = to_money(
            customer_totals.get(row.customer_id, ZERO_MONEY) + outstanding_base
        )

        if row.due_date is None or row.due_date >= snapshot_date:
            bucket_key = "not_due"
        else:
            overdue_days = (snapshot_date - row.due_date).days
            overdue_count += 1
            if overdue_days <= 30:
                bucket_key = "1_30"
            elif overdue_days <= 60:
                bucket_key = "31_60"
            elif overdue_days <= 90:
                bucket_key = "61_90"
            else:
                bucket_key = "91_plus"
        bucket_totals[bucket_key] = to_money(bucket_totals[bucket_key] + outstanding_base)
        bucket_counts[bucket_key] += 1

    sorted_customers = sorted(
        customer_totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    customer_name_map = get_customer_name_map(
        db,
        business_id=access.business.id,
        customer_ids=[customer_id for customer_id, _amount in sorted_customers],
    )

    return InvoiceAgingDashboardOut(
        as_of_date=snapshot_date,
        base_currency=access.business.base_currency,
        total_outstanding=float(to_money(total_outstanding_base)),
        overdue_count=overdue_count,
        partially_paid_count=partially_paid_count,
        buckets=[
            InvoiceAgingBucketOut(bucket=bucket, amount=float(to_money(amount)), count=bucket_counts[bucket])
            for bucket, amount in bucket_totals.items()
        ],
        by_currency={currency: float(to_money(amount)) for currency, amount in by_currency.items()},
        top_customers=[
            InvoiceAgingCustomerOut(
                customer_id=customer_id,
                customer_name=customer_name_map.get(customer_id or ""),
                amount=float(to_money(amount)),
                count=0,
            )
            for customer_id, amount in sorted_customers
        ],
    )


def _build_statement_items(
    db: Session,
    *,
    business_id: str,
    start_date: date,
    end_date: date,
) -> list[InvoiceStatementItemOut]:
    rows = db.execute(
        select(Invoice).where(
            Invoice.business_id == business_id,
            Invoice.issue_date >= start_date,
            Invoice.issue_date <= end_date,
        )
    ).scalars().all()

    grouped: dict[str | None, dict] = {}
    for row in rows:
        key = row.customer_id
        grouped.setdefault(
            key,
            {
                "invoices_count": 0,
                "total_invoiced": ZERO_MONEY,
                "total_paid": ZERO_MONEY,
                "total_outstanding": ZERO_MONEY,
                "by_currency": {},
            },
        )
        current = grouped[key]
        current["invoices_count"] += 1
        current["total_invoiced"] = to_money(current["total_invoiced"] + to_money(row.total_amount_base))
        current["total_paid"] = to_money(current["total_paid"] + to_money(row.amount_paid_base))
        current["total_outstanding"] = to_money(
            current["total_outstanding"] + _outstanding_amount_base(row)
        )
        by_currency = current["by_currency"]
        by_currency[row.currency] = to_money(by_currency.get(row.currency, ZERO_MONEY) + _outstanding_amount(row))
    customer_name_map = get_customer_name_map(
        db,
        business_id=business_id,
        customer_ids=list(grouped.keys()),
    )

    out = [
        InvoiceStatementItemOut(
            customer_id=customer_id,
            customer_name=customer_name_map.get(customer_id or ""),
            invoices_count=payload["invoices_count"],
            total_invoiced=float(to_money(payload["total_invoiced"])),
            total_paid=float(to_money(payload["total_paid"])),
            total_outstanding=float(to_money(payload["total_outstanding"])),
            by_currency={
                currency: float(to_money(amount))
                for currency, amount in payload["by_currency"].items()
            },
        )
        for customer_id, payload in grouped.items()
    ]
    out.sort(key=lambda row: row.total_outstanding, reverse=True)
    return out


@router.get(
    "/statements",
    response_model=InvoiceStatementListOut,
    summary="Monthly statements summary",
    responses=error_responses(400, 401, 403, 422, 500),
)
def list_statements(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _validate_date_range(start_date, end_date)
    return InvoiceStatementListOut(
        items=_build_statement_items(
            db,
            business_id=access.business.id,
            start_date=start_date,
            end_date=end_date,
        ),
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/statements/export",
    response_model=InvoiceStatementExportOut,
    summary="Export monthly statements as CSV payload",
    responses=error_responses(400, 401, 403, 422, 500),
)
def export_statements(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _validate_date_range(start_date, end_date)
    items = _build_statement_items(
        db,
        business_id=access.business.id,
        start_date=start_date,
        end_date=end_date,
    )
    writer_buffer = io.StringIO()
    writer = csv.DictWriter(
        writer_buffer,
        fieldnames=[
            "customer_id",
            "customer_name",
            "invoices_count",
            "total_invoiced",
            "total_paid",
            "total_outstanding",
            "by_currency",
        ],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "customer_id": item.customer_id or "",
                "customer_name": item.customer_name or "",
                "invoices_count": item.invoices_count,
                "total_invoiced": item.total_invoiced,
                "total_paid": item.total_paid,
                "total_outstanding": item.total_outstanding,
                "by_currency": json.dumps(item.by_currency, separators=(",", ":")),
            }
        )
    return InvoiceStatementExportOut(
        filename=f"invoice_statements_{start_date.isoformat()}_{end_date.isoformat()}.csv",
        content_type="text/csv",
        row_count=len(items),
        csv_content=writer_buffer.getvalue(),
    )


@router.post(
    "/reminders/run-due",
    response_model=InvoiceReminderRunOut,
    summary="Run due reminder automation",
    responses=error_responses(401, 403, 422, 500),
)
def run_due_reminders(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Invoice).where(
            Invoice.business_id == access.business.id,
            Invoice.status.in_(["sent", "partially_paid", "overdue"]),
            Invoice.next_reminder_at.is_not(None),
            Invoice.next_reminder_at <= now,
        )
    ).scalars().all()

    processed_count = 0
    reminders_created = 0
    escalated_count = 0
    next_due_count = 0
    for row in rows:
        processed_count += 1
        policy = _reminder_policy_for_invoice(row)
        if not policy.get("enabled", False):
            row.next_reminder_at = None
            continue
        if _outstanding_amount(row) <= ZERO_MONEY:
            row.next_reminder_at = None
            continue
        if int(row.reminder_count or 0) >= int(policy["max_reminders"]):
            row.next_reminder_at = None
            continue

        row.reminder_count = int(row.reminder_count or 0) + 1
        reminders_created += 1
        _record_invoice_event(
            db,
            invoice=row,
            event_type="reminder_auto",
            metadata_json={"channels": list(policy["channels"]), "run_at": now.isoformat()},
        )

        if row.due_date and (date.today() - row.due_date).days >= int(policy["escalation_after_days"]):
            row.escalation_level = int(row.escalation_level or 0) + 1
            escalated_count += 1
            _record_invoice_event(
                db,
                invoice=row,
                event_type="reminder_escalated",
                metadata_json={"escalation_level": row.escalation_level},
            )
            row.status = "overdue"

        if int(row.reminder_count or 0) >= int(policy["max_reminders"]):
            row.next_reminder_at = None
        else:
            row.next_reminder_at = now + timedelta(days=int(policy["cadence_days"]))
            next_due_count += 1

    if processed_count > 0:
        log_audit_event(
            db,
            business_id=access.business.id,
            actor_user_id=actor.id,
            action="invoice.reminder.run_due",
            target_type="invoice",
            target_id=None,
            metadata_json={
                "processed_count": processed_count,
                "reminders_created": reminders_created,
                "escalated_count": escalated_count,
                "next_due_count": next_due_count,
            },
        )
    db.commit()
    return InvoiceReminderRunOut(
        processed_count=processed_count,
        reminders_created=reminders_created,
        escalated_count=escalated_count,
        next_due_count=next_due_count,
    )


@router.post(
    "",
    response_model=InvoiceCreateOut,
    summary="Create invoice",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    customer_id = payload.customer_id
    order: Order | None = None
    if payload.order_id:
        order = db.execute(
            select(Order).where(
                Order.id == payload.order_id,
                Order.business_id == access.business.id,
            )
        ).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.customer_id:
            if customer_id and customer_id != order.customer_id:
                raise HTTPException(status_code=400, detail="customer_id must match linked order customer")
            customer_id = order.customer_id

    if customer_id and not _customer_exists(db, business_id=access.business.id, customer_id=customer_id):
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = _customer_for_invoice(
        db,
        business_id=access.business.id,
        customer_id=customer_id,
    )

    if payload.total_amount is None and order is None:
        raise HTTPException(status_code=400, detail="Provide total_amount or link an order")

    total_amount = to_money(payload.total_amount if payload.total_amount is not None else order.total_amount)
    if total_amount <= ZERO_MONEY:
        raise HTTPException(status_code=400, detail="Invoice total_amount must be greater than zero")

    currency = _normalize_currency(payload.currency)
    base_currency = _normalize_currency(access.business.base_currency)
    fx_rate = (
        _to_rate(payload.fx_rate_to_base)
        if payload.fx_rate_to_base is not None
        else _lookup_fx_rate(currency, base_currency)
    )
    if currency == base_currency:
        fx_rate = Decimal("1.000000")
    total_amount_base = to_money(total_amount * fx_rate)

    _ensure_invoice_template_belongs_to_business(
        db,
        business_id=access.business.id,
        template_id=payload.template_id,
    )

    issue_date = payload.issue_date or date.today()
    invoice = Invoice(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        customer_id=customer_id,
        order_id=payload.order_id,
        status="draft",
        currency=currency,
        base_currency=base_currency,
        fx_rate_to_base=fx_rate,
        total_amount=total_amount,
        total_amount_base=total_amount_base,
        amount_paid=ZERO_MONEY,
        amount_paid_base=ZERO_MONEY,
        template_id=payload.template_id,
        reminder_policy_json=(
            payload.reminder_policy.model_dump() if payload.reminder_policy is not None else None
        ),
        issue_date=issue_date,
        due_date=payload.due_date,
        note=payload.note,
    )
    db.add(invoice)
    db.flush()

    if payload.installments:
        scheduled_total = ZERO_MONEY
        for item in payload.installments:
            if item.due_date < issue_date:
                raise HTTPException(status_code=400, detail="installment due_date cannot be before issue_date")
            scheduled_total += to_money(item.amount)
        if scheduled_total > total_amount:
            raise HTTPException(status_code=400, detail="Installment schedule cannot exceed invoice total")
        for item in payload.installments:
            db.add(
                InvoiceInstallment(
                    id=str(uuid.uuid4()),
                    invoice_id=invoice.id,
                    business_id=access.business.id,
                    due_date=item.due_date,
                    amount=to_money(item.amount),
                    paid_amount=ZERO_MONEY,
                    status="overdue" if item.due_date < date.today() else "pending",
                    note=item.note,
                )
            )

    _record_invoice_event(
        db,
        invoice=invoice,
        event_type="create",
        metadata_json={
            "customer_id": customer_id,
            "customer_name": customer.name if customer else None,
            "order_id": payload.order_id,
            "currency": currency,
            "total_amount": float(total_amount),
        },
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="invoice.create",
        target_type="invoice",
        target_id=invoice.id,
        metadata_json={
            "customer_id": customer_id,
            "customer_name": customer.name if customer else None,
            "order_id": payload.order_id,
            "status": invoice.status,
            "total_amount": float(total_amount),
            "currency": currency,
        },
    )

    if payload.send_now:
        delivery_channel, recipient = _send_invoice_now(
            db,
            invoice=invoice,
            customer=customer,
            channel=payload.send_channel,
            recipient_override=payload.send_recipient_override,
            note=payload.send_note,
            event_type="send",
        )
        log_audit_event(
            db,
            business_id=access.business.id,
            actor_user_id=actor.id,
            action="invoice.send",
            target_type="invoice",
            target_id=invoice.id,
            metadata_json={
                "status": invoice.status,
                "channel": delivery_channel,
                "recipient": recipient,
                "customer_name": customer.name if customer else None,
            },
        )

    db.commit()
    db.refresh(invoice)
    return InvoiceCreateOut(
        id=invoice.id,
        status=invoice.status,
        total_amount=float(to_money(invoice.total_amount)),
        total_amount_base=float(to_money(invoice.total_amount_base)),
        currency=invoice.currency,
        base_currency=invoice.base_currency,
    )


@router.get(
    "/{invoice_id}/preview",
    response_model=InvoicePreviewOut,
    summary="Preview invoice content and delivery readiness",
    responses=error_responses(401, 403, 404, 422, 500),
)
def preview_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    return _build_invoice_preview(
        db,
        business_name=access.business.name,
        invoice=invoice,
    )


@router.get(
    "",
    response_model=InvoiceListOut,
    summary="List invoices",
    responses=error_responses(400, 401, 403, 422, 500),
)
def list_invoices(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _validate_date_range(start_date, end_date)
    overdue_updates = _auto_mark_overdue_invoices(db, business_id=access.business.id)
    if overdue_updates > 0:
        db.commit()

    normalized_status = None
    if status and status.strip():
        normalized_status = status.strip().lower()
        if normalized_status not in ALLOWED_INVOICE_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_INVOICE_STATUSES))
            raise HTTPException(status_code=400, detail=f"Invalid invoice status. Allowed: {allowed}")

    count_stmt = select(func.count(Invoice.id)).where(Invoice.business_id == access.business.id)
    stmt = select(Invoice).where(Invoice.business_id == access.business.id)

    if normalized_status:
        count_stmt = count_stmt.where(Invoice.status == normalized_status)
        stmt = stmt.where(Invoice.status == normalized_status)
    if customer_id:
        count_stmt = count_stmt.where(Invoice.customer_id == customer_id)
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if order_id:
        count_stmt = count_stmt.where(Invoice.order_id == order_id)
        stmt = stmt.where(Invoice.order_id == order_id)
    if start_date:
        count_stmt = count_stmt.where(func.date(Invoice.created_at) >= start_date)
        stmt = stmt.where(func.date(Invoice.created_at) >= start_date)
    if end_date:
        count_stmt = count_stmt.where(func.date(Invoice.created_at) <= end_date)
        stmt = stmt.where(func.date(Invoice.created_at) <= end_date)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    customer_name_map = get_customer_name_map(
        db,
        business_id=access.business.id,
        customer_ids=[row.customer_id for row in rows],
    )
    items = [
        _invoice_out(row, customer_name=customer_name_map.get(row.customer_id or ""))
        for row in rows
    ]
    count = len(items)
    return InvoiceListOut(
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        start_date=start_date,
        end_date=end_date,
        status=normalized_status,
        customer_id=customer_id,
        order_id=order_id,
        items=items,
    )


@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceOut,
    summary="Send invoice",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def send_invoice(
    invoice_id: str,
    payload: InvoiceSendIn | None = None,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    customer = _customer_for_invoice(
        db,
        business_id=access.business.id,
        customer_id=invoice.customer_id,
    )
    delivery_channel, recipient = _send_invoice_now(
        db,
        invoice=invoice,
        customer=customer,
        channel=payload.channel if payload else None,
        recipient_override=payload.recipient_override if payload else None,
        note=payload.note if payload else None,
        event_type="send",
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="invoice.send",
        target_type="invoice",
        target_id=invoice.id,
        metadata_json={
            "status": invoice.status,
            "channel": delivery_channel,
            "recipient": recipient,
            "customer_name": customer.name if customer else None,
        },
    )
    db.commit()
    db.refresh(invoice)
    customer_name_map = get_customer_name_map(
        db,
        business_id=access.business.id,
        customer_ids=[invoice.customer_id],
    )
    return _invoice_out(invoice, customer_name=customer_name_map.get(invoice.customer_id or ""))


@router.post(
    "/{invoice_id}/reminders",
    response_model=InvoiceOut,
    summary="Trigger manual reminder",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def remind_invoice(
    invoice_id: str,
    payload: InvoiceReminderIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    if invoice.status in {"paid", "cancelled"}:
        raise HTTPException(status_code=400, detail="Cannot remind paid/cancelled invoice")
    if invoice.status not in {"sent", "overdue", "partially_paid"}:
        raise HTTPException(status_code=400, detail="Invoice must be sent before reminders")
    customer = _customer_for_invoice(
        db,
        business_id=access.business.id,
        customer_id=invoice.customer_id,
    )
    delivery_channel, recipient = _resolve_invoice_delivery_target(
        customer=customer,
        channel=payload.channel,
        recipient_override=payload.recipient_override,
    )

    invoice.reminder_count = int(invoice.reminder_count or 0) + 1
    policy = _reminder_policy_for_invoice(invoice)
    if policy.get("enabled", False):
        if int(invoice.reminder_count) >= int(policy["max_reminders"]):
            invoice.next_reminder_at = None
        else:
            invoice.next_reminder_at = datetime.now(timezone.utc) + timedelta(
                days=int(policy["cadence_days"])
            )
    _record_invoice_event(
        db,
        invoice=invoice,
        event_type="reminder_manual",
        metadata_json={
            "channel": delivery_channel,
            "recipient": recipient,
            "note": payload.note,
            "delivery_status": "sent",
        },
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="invoice.reminder.manual",
        target_type="invoice",
        target_id=invoice.id,
        metadata_json={
            "channel": delivery_channel,
            "recipient": recipient,
            "customer_name": customer.name if customer else None,
        },
    )
    db.commit()
    db.refresh(invoice)
    customer_name_map = get_customer_name_map(
        db,
        business_id=access.business.id,
        customer_ids=[invoice.customer_id],
    )
    return _invoice_out(invoice, customer_name=customer_name_map.get(invoice.customer_id or ""))


@router.patch(
    "/{invoice_id}/mark-paid",
    response_model=InvoiceOut,
    summary="Mark invoice paid (supports partial amount)",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def mark_invoice_paid(
    invoice_id: str,
    payload: InvoiceMarkPaidIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    if payload.idempotency_key:
        existing = db.execute(
            select(InvoiceEvent.id).where(
                InvoiceEvent.business_id == access.business.id,
                InvoiceEvent.invoice_id == invoice.id,
                InvoiceEvent.event_type == "mark_paid",
                InvoiceEvent.idempotency_key == payload.idempotency_key,
            )
        ).scalar_one_or_none()
        if existing:
            customer_name_map = get_customer_name_map(
                db,
                business_id=access.business.id,
                customer_ids=[invoice.customer_id],
            )
            return _invoice_out(invoice, customer_name=customer_name_map.get(invoice.customer_id or ""))

    if _outstanding_amount(invoice) <= ZERO_MONEY:
        customer_name_map = get_customer_name_map(
            db,
            business_id=access.business.id,
            customer_ids=[invoice.customer_id],
        )
        return _invoice_out(invoice, customer_name=customer_name_map.get(invoice.customer_id or ""))

    payment = _apply_payment(
        db,
        invoice=invoice,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        idempotency_key=payload.idempotency_key,
        note=payload.note,
        paid_at=None,
        event_type="mark_paid",
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="invoice.mark_paid",
        target_type="invoice",
        target_id=invoice.id,
        metadata_json={
            "amount": float(to_money(payment.amount)),
            "currency": payment.currency,
            "payment_reference": payment.payment_reference,
            "idempotency_key": payment.idempotency_key,
        },
    )
    db.commit()
    db.refresh(invoice)
    customer_name_map = get_customer_name_map(
        db,
        business_id=access.business.id,
        customer_ids=[invoice.customer_id],
    )
    return _invoice_out(invoice, customer_name=customer_name_map.get(invoice.customer_id or ""))


@router.post(
    "/{invoice_id}/payments",
    response_model=InvoicePaymentOut,
    summary="Record partial payment against invoice",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_invoice_payment(
    invoice_id: str,
    payload: InvoicePaymentCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    if payload.idempotency_key:
        existing = db.execute(
            select(InvoicePayment).where(
                InvoicePayment.business_id == access.business.id,
                InvoicePayment.invoice_id == invoice.id,
                InvoicePayment.idempotency_key == payload.idempotency_key,
            )
        ).scalar_one_or_none()
        if existing:
            return _payment_out(existing)

    payment = _apply_payment(
        db,
        invoice=invoice,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        idempotency_key=payload.idempotency_key,
        note=payload.note,
        paid_at=payload.paid_at,
        event_type="payment_recorded",
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="invoice.payment.record",
        target_type="invoice_payment",
        target_id=payment.id,
        metadata_json={
            "invoice_id": invoice.id,
            "amount": float(to_money(payment.amount)),
            "currency": payment.currency,
        },
    )
    db.commit()
    db.refresh(payment)
    return _payment_out(payment)


@router.get(
    "/{invoice_id}/payments",
    response_model=InvoicePaymentListOut,
    summary="List invoice payments",
    responses=error_responses(401, 403, 404, 422, 500),
)
def list_invoice_payments(
    invoice_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    count_stmt = select(func.count(InvoicePayment.id)).where(
        InvoicePayment.business_id == access.business.id,
        InvoicePayment.invoice_id == invoice.id,
    )
    stmt = select(InvoicePayment).where(
        InvoicePayment.business_id == access.business.id,
        InvoicePayment.invoice_id == invoice.id,
    )
    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(InvoicePayment.paid_at.desc(), InvoicePayment.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    items = [_payment_out(row) for row in rows]
    count = len(items)
    return InvoicePaymentListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )


@router.put(
    "/{invoice_id}/installments",
    response_model=InvoiceInstallmentListOut,
    summary="Create or replace installment schedule for an invoice",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def upsert_invoice_installments(
    invoice_id: str,
    payload: InvoiceInstallmentUpsertIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    _ensure_invoice_not_cancelled(invoice)

    total = ZERO_MONEY
    for item in payload.items:
        if item.due_date < invoice.issue_date:
            raise HTTPException(status_code=400, detail="installment due_date cannot be before invoice issue_date")
        total += to_money(item.amount)
    if total > to_money(invoice.total_amount):
        raise HTTPException(status_code=400, detail="Installment schedule cannot exceed invoice total")

    db.execute(
        delete(InvoiceInstallment).where(
            InvoiceInstallment.business_id == access.business.id,
            InvoiceInstallment.invoice_id == invoice.id,
        )
    )
    for item in payload.items:
        db.add(
            InvoiceInstallment(
                id=str(uuid.uuid4()),
                invoice_id=invoice.id,
                business_id=access.business.id,
                due_date=item.due_date,
                amount=to_money(item.amount),
                paid_amount=ZERO_MONEY,
                status="overdue" if item.due_date < date.today() else "pending",
                note=item.note,
            )
        )
    _sync_installments_from_paid_amount(db, invoice=invoice)
    _record_invoice_event(
        db,
        invoice=invoice,
        event_type="installments_upsert",
        metadata_json={"items_count": len(payload.items)},
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="invoice.installments.upsert",
        target_type="invoice",
        target_id=invoice.id,
        metadata_json={"items_count": len(payload.items)},
    )
    db.commit()
    return _installment_list_out(db, invoice=invoice)


@router.get(
    "/{invoice_id}/installments",
    response_model=InvoiceInstallmentListOut,
    summary="List invoice installment schedule",
    responses=error_responses(401, 403, 404, 422, 500),
)
def list_invoice_installments(
    invoice_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    return _installment_list_out(db, invoice=invoice)


@router.put(
    "/{invoice_id}/reminder-policy",
    response_model=InvoiceReminderPolicyOut,
    summary="Set invoice reminder policy",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def upsert_reminder_policy(
    invoice_id: str,
    payload: InvoiceReminderPolicyIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    invoice.reminder_policy_json = payload.model_dump()
    if payload.enabled:
        invoice.next_reminder_at = _compute_next_reminder_at(
            invoice=invoice,
            policy=payload.model_dump(),
            now=datetime.now(timezone.utc),
            reset_first=invoice.next_reminder_at is None,
        )
    else:
        invoice.next_reminder_at = None

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="invoice.reminder_policy.update",
        target_type="invoice",
        target_id=invoice.id,
        metadata_json={"enabled": payload.enabled},
    )
    db.commit()
    db.refresh(invoice)
    return _to_policy_out(invoice)


@router.get(
    "/{invoice_id}/reminder-policy",
    response_model=InvoiceReminderPolicyOut,
    summary="Get invoice reminder policy",
    responses=error_responses(401, 403, 404, 422, 500),
)
def get_reminder_policy(
    invoice_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    invoice = _invoice_or_404(db, business_id=access.business.id, invoice_id=invoice_id)
    return _to_policy_out(invoice)
