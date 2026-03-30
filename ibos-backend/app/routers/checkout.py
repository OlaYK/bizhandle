import hashlib
import hmac
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.config import settings
from app.core.deps import get_db
from app.core.money import ZERO_MONEY, to_money
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.business import Business
from app.models.checkout import CheckoutSession, CheckoutSessionItem, CheckoutWebhookEvent
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductVariant
from app.models.storefront import StorefrontConfig
from app.models.user import User
from app.routers.orders import (
    _convert_order_to_sale,
    _ensure_transition_allowed,
    _normalize_order_status,
)
from app.schemas.checkout import (
    CheckoutPaymentsSummaryOut,
    CheckoutSessionCreateIn,
    CheckoutSessionCreateOut,
    CheckoutSessionItemOut,
    CheckoutSessionListOut,
    CheckoutSessionOut,
    CheckoutSessionPlaceOrderIn,
    CheckoutSessionPlaceOrderOut,
    CheckoutSessionPublicOut,
    StorefrontCheckoutSessionCreateIn,
    StorefrontCartSessionCreateIn,
    CheckoutSessionRetryPaymentOut,
    CheckoutWebhookEventIn,
    CheckoutWebhookOut,
)
from app.schemas.common import PaginationMeta
from app.services.audit_service import log_audit_event
from app.services.display_service import (
    build_display_reference,
    get_customer_name_map,
    get_variant_display_map,
)
from app.services.payment_provider import PaymentInitRequest, get_payment_provider

router = APIRouter(prefix="/checkout", tags=["checkout"])
management_router = APIRouter(prefix="/checkout-sessions", tags=["checkout"])
webhooks_router = APIRouter(prefix="/payment-webhooks", tags=["checkout"])

ALLOWED_SESSION_STATUSES = {
    "open",
    "pending_payment",
    "payment_failed",
    "paid",
    "expired",
}


def _variant_business_map(db: Session, variant_ids: list[str]) -> dict[str, str]:
    rows = db.execute(
        select(ProductVariant.id, ProductVariant.business_id).where(ProductVariant.id.in_(variant_ids))
    ).all()
    return {variant_id: business_id for variant_id, business_id in rows}


def _resolve_customer_id(db: Session, *, business_id: str, customer_id: str | None) -> str | None:
    if not customer_id:
        return None
    normalized = customer_id.strip()
    if not normalized:
        return None
    customer = db.execute(
        select(Customer.id).where(
            Customer.id == normalized,
            Customer.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return normalized


def _resolve_or_create_checkout_customer_id(
    db: Session,
    *,
    business_id: str,
    customer_id: str | None,
    customer_name: str | None,
    customer_email: str | None,
    customer_phone: str | None,
) -> str | None:
    resolved_customer_id = _resolve_customer_id(
        db,
        business_id=business_id,
        customer_id=customer_id,
    )
    if resolved_customer_id:
        return resolved_customer_id

    normalized_name = (customer_name or "").strip() or None
    normalized_email = (customer_email or "").strip().lower() or None
    normalized_phone = (customer_phone or "").strip() or None
    if not any([normalized_name, normalized_email, normalized_phone]):
        return None
    if not normalized_name:
        raise HTTPException(status_code=400, detail="customer_name is required for guest checkout")

    existing_customer = None
    if normalized_email:
        existing_customer = db.execute(
            select(Customer).where(
                Customer.business_id == business_id,
                func.lower(Customer.email) == normalized_email,
            )
        ).scalar_one_or_none()
    if not existing_customer and normalized_phone:
        existing_customer = db.execute(
            select(Customer).where(
                Customer.business_id == business_id,
                Customer.phone == normalized_phone,
            )
        ).scalar_one_or_none()
    if existing_customer:
        if normalized_name and existing_customer.name != normalized_name:
            existing_customer.name = normalized_name
        if normalized_email and not existing_customer.email:
            existing_customer.email = normalized_email
        if normalized_phone and not existing_customer.phone:
            existing_customer.phone = normalized_phone
        return existing_customer.id

    new_customer = Customer(
        id=str(uuid.uuid4()),
        business_id=business_id,
        name=normalized_name,
        email=normalized_email,
        phone=normalized_phone,
        note="Created from public checkout",
    )
    db.add(new_customer)
    db.flush()
    return new_customer.id


def _checkout_by_token_or_404(db: Session, *, session_token: str) -> CheckoutSession:
    checkout = db.execute(
        select(CheckoutSession).where(CheckoutSession.session_token == session_token)
    ).scalar_one_or_none()
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    return checkout


def _checkout_by_id_or_404(
    db: Session,
    *,
    checkout_session_id: str,
    business_id: str | None = None,
) -> CheckoutSession:
    stmt = select(CheckoutSession).where(CheckoutSession.id == checkout_session_id)
    if business_id:
        stmt = stmt.where(CheckoutSession.business_id == business_id)
    checkout = db.execute(stmt).scalar_one_or_none()
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    return checkout


def _normalize_session_status(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned not in ALLOWED_SESSION_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_SESSION_STATUSES))
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {allowed}")
    return cleaned


def _mark_session_expired_if_needed(checkout: CheckoutSession) -> bool:
    now = datetime.now(timezone.utc)
    expires_at = (
        checkout.expires_at.replace(tzinfo=timezone.utc)
        if checkout.expires_at.tzinfo is None
        else checkout.expires_at.astimezone(timezone.utc)
    )
    if checkout.status in {"open", "pending_payment", "payment_failed"} and expires_at <= now:
        checkout.status = "expired"
        return True
    return False


def _init_provider_checkout(
    *,
    checkout: CheckoutSession,
    total_amount: float,
) -> None:
    provider = get_payment_provider(settings.payment_provider_default)
    payment_result = provider.initialize_checkout(
        PaymentInitRequest(
            business_id=checkout.business_id,
            checkout_session_id=checkout.id,
            checkout_session_token=checkout.session_token,
            amount=total_amount,
            currency=checkout.currency,
            success_redirect_url=checkout.success_redirect_url,
            cancel_redirect_url=checkout.cancel_redirect_url,
        )
    )
    checkout.payment_provider = payment_result.provider
    checkout.payment_reference = payment_result.payment_reference
    checkout.payment_checkout_url = payment_result.checkout_url


def _checkout_out(
    db: Session,
    checkout: CheckoutSession,
    *,
    order_lookup: dict[str, dict[str, object]] | None = None,
    customer_name_map: dict[str, str] | None = None,
) -> CheckoutSessionOut:
    order_payload: dict[str, object] | None = None
    if order_lookup is not None:
        order_payload = order_lookup.get(checkout.order_id or "")
    elif checkout.order_id:
        order = db.execute(
            select(Order).where(
                Order.id == checkout.order_id,
                Order.business_id == checkout.business_id,
            )
        ).scalar_one_or_none()
        if order:
            order_payload = {
                "status": order.status,
                "sale_id": order.sale_id,
            }

    customer_name = None
    if customer_name_map is not None:
        customer_name = customer_name_map.get(checkout.customer_id or "")
    elif checkout.customer_id:
        customer_name = db.execute(
            select(Customer.name).where(
                Customer.id == checkout.customer_id,
                Customer.business_id == checkout.business_id,
            )
        ).scalar_one_or_none()

    return CheckoutSessionOut(
        id=checkout.id,
        session_token=checkout.session_token,
        status=checkout.status,
        currency=checkout.currency,
        customer_id=checkout.customer_id,
        customer_name=customer_name,
        payment_method=checkout.payment_method,
        channel=checkout.channel,
        total_amount=float(to_money(checkout.total_amount)),
        payment_provider=checkout.payment_provider,
        payment_reference=checkout.payment_reference,
        payment_checkout_url=checkout.payment_checkout_url,
        order_id=checkout.order_id,
        order_reference=build_display_reference("ORD", checkout.order_id),
        order_status=str(order_payload["status"]) if order_payload else None,
        sale_id=str(order_payload["sale_id"]) if order_payload and order_payload.get("sale_id") else None,
        has_sale=bool(order_payload and order_payload.get("sale_id")),
        created_at=checkout.created_at,
        updated_at=checkout.updated_at,
        expires_at=checkout.expires_at,
    )


def _checkout_public_items(db: Session, checkout: CheckoutSession) -> list[CheckoutSessionItemOut]:
    items = db.execute(
        select(CheckoutSessionItem).where(CheckoutSessionItem.checkout_session_id == checkout.id)
    ).scalars().all()
    variant_display_map = get_variant_display_map(
        db,
        business_id=checkout.business_id,
        variant_ids=[item.variant_id for item in items],
    )
    return [
        CheckoutSessionItemOut(
            variant_id=item.variant_id,
            product_id=variant_display_map.get(item.variant_id).product_id
            if item.variant_id in variant_display_map
            else None,
            product_name=variant_display_map.get(item.variant_id).product_name
            if item.variant_id in variant_display_map
            else None,
            size=variant_display_map.get(item.variant_id).size
            if item.variant_id in variant_display_map
            else None,
            label=variant_display_map.get(item.variant_id).label
            if item.variant_id in variant_display_map
            else None,
            sku=variant_display_map.get(item.variant_id).sku
            if item.variant_id in variant_display_map
            else None,
            qty=item.qty,
            unit_price=float(to_money(item.unit_price)),
            line_total=float(to_money(item.line_total)),
        )
        for item in items
    ]


def _storefront_cart_rows_or_404(
    db: Session,
    *,
    storefront: StorefrontConfig,
    variant_ids: list[str],
) -> dict[str, tuple[ProductVariant, Product]]:
    rows = db.execute(
        select(ProductVariant, Product)
        .join(
            Product,
            (Product.id == ProductVariant.product_id)
            & (Product.business_id == ProductVariant.business_id),
        )
        .where(
            ProductVariant.id.in_(variant_ids),
            ProductVariant.business_id == storefront.business_id,
            ProductVariant.is_published.is_(True),
            Product.business_id == storefront.business_id,
            Product.active.is_(True),
            Product.is_published.is_(True),
        )
    ).all()
    row_map = {variant.id: (variant, product) for variant, product in rows}
    missing = [variant_id for variant_id in variant_ids if variant_id not in row_map]
    if missing:
        raise HTTPException(status_code=404, detail=f"Variant not available on this storefront: {missing[0]}")
    return row_map


def _public_storefront_or_404(db: Session, *, slug: str) -> StorefrontConfig:
    storefront = db.execute(
        select(StorefrontConfig).where(
            func.lower(StorefrontConfig.slug) == slug.strip().lower(),
            StorefrontConfig.is_published.is_(True),
        )
    ).scalar_one_or_none()
    if not storefront:
        raise HTTPException(status_code=404, detail="Storefront not found")
    return storefront


def _create_storefront_checkout_session(
    db: Session,
    *,
    storefront: StorefrontConfig,
    items: list[tuple[str, int]],
    audit_action: str,
    payment_method: str,
    channel: str,
    note: str | None,
    success_redirect_url: str | None,
    cancel_redirect_url: str | None,
    expires_in_minutes: int,
) -> CheckoutSession:
    variant_ids = [variant_id for variant_id, _qty in items]
    row_map = _storefront_cart_rows_or_404(
        db,
        storefront=storefront,
        variant_ids=variant_ids,
    )

    business = db.execute(select(Business).where(Business.id == storefront.business_id)).scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Storefront business not found")

    qty_by_variant: dict[str, int] = {}
    for variant_id, qty in items:
        qty_by_variant[variant_id] = qty_by_variant.get(variant_id, 0) + qty

    checkout = CheckoutSession(
        id=str(uuid.uuid4()),
        business_id=storefront.business_id,
        session_token=uuid.uuid4().hex,
        status="open",
        currency=business.base_currency.upper(),
        payment_method=payment_method,
        channel=channel,
        note=note,
        total_amount=ZERO_MONEY,
        success_redirect_url=success_redirect_url,
        cancel_redirect_url=cancel_redirect_url,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
    )
    db.add(checkout)

    total = ZERO_MONEY
    for variant_id, qty in qty_by_variant.items():
        variant, _product = row_map[variant_id]
        if variant.selling_price is None or to_money(variant.selling_price) <= ZERO_MONEY:
            raise HTTPException(status_code=400, detail=f"Variant has no valid selling price: {variant_id}")
        unit_price = to_money(variant.selling_price)
        line_total = to_money(unit_price * qty)
        total += line_total
        db.add(
            CheckoutSessionItem(
                id=str(uuid.uuid4()),
                checkout_session_id=checkout.id,
                variant_id=variant_id,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    checkout.total_amount = to_money(total)
    _init_provider_checkout(checkout=checkout, total_amount=float(to_money(total)))

    log_audit_event(
        db,
        business_id=storefront.business_id,
        actor_user_id=business.owner_user_id,
        action=audit_action,
        target_type="checkout_session",
        target_id=checkout.id,
        metadata_json={
            "slug": storefront.slug,
            "items_count": len(qty_by_variant),
            "units_total": sum(qty_by_variant.values()),
            "currency": checkout.currency,
            "payment_method": checkout.payment_method,
            "channel": checkout.channel,
            "total_amount": float(to_money(total)),
            "payment_provider": checkout.payment_provider,
        },
    )
    return checkout


def _build_webhook_signature(payload_bytes: bytes) -> str:
    digest = hmac.new(
        settings.payment_webhook_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _assert_webhook_signature(payload_bytes: bytes, signature_header: str | None) -> None:
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    expected = _build_webhook_signature(payload_bytes)
    provided = signature_header.strip()
    if provided.startswith("sha256="):
        provided = provided
    else:
        provided = f"sha256={provided}"

    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _sync_order_paid_from_checkout(
    db: Session,
    *,
    checkout: CheckoutSession,
    actor_user_id: str,
    webhook_event_id: str,
) -> tuple[str | None, str | None]:
    if not checkout.order_id:
        return None, None

    order = db.execute(
        select(Order).where(
            Order.id == checkout.order_id,
            Order.business_id == checkout.business_id,
        )
    ).scalar_one_or_none()
    if not order:
        return None, None

    current_status = _normalize_order_status(order.status)
    target_status = "paid"
    _ensure_transition_allowed(current_status, target_status)

    if current_status != target_status:
        order.status = target_status

    converted_sale_id: str | None = None
    if order.sale_id is None:
        order_items = db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).scalars().all()
        converted_sale_id = _convert_order_to_sale(
            db,
            order=order,
            order_items=order_items,
            actor_user_id=actor_user_id,
        )

    log_audit_event(
        db,
        business_id=checkout.business_id,
        actor_user_id=actor_user_id,
        action="checkout.webhook.auto_mark_paid",
        target_type="order",
        target_id=order.id,
        metadata_json={
            "checkout_session_id": checkout.id,
            "webhook_event_id": webhook_event_id,
            "order_status": order.status,
            "sale_id": order.sale_id,
            "converted_sale_id": converted_sale_id,
        },
    )
    return order.id, order.status


@management_router.post(
    "",
    response_model=CheckoutSessionCreateOut,
    summary="Create checkout session",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_checkout_session(
    payload: CheckoutSessionCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    business_id = access.business.id
    resolved_customer_id = _resolve_customer_id(
        db,
        business_id=business_id,
        customer_id=payload.customer_id,
    )

    quantity_by_variant: dict[str, int] = {}
    total = ZERO_MONEY
    for item in payload.items:
        quantity_by_variant[item.variant_id] = quantity_by_variant.get(item.variant_id, 0) + item.qty
        total += to_money(item.unit_price) * item.qty

    variant_ids = list(quantity_by_variant.keys())
    business_by_variant = _variant_business_map(db, variant_ids)
    for variant_id in variant_ids:
        variant_business = business_by_variant.get(variant_id)
        if not variant_business:
            raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")
        if variant_business != business_id:
            raise HTTPException(status_code=403, detail="Contains item not in your business")

    checkout = CheckoutSession(
        id=str(uuid.uuid4()),
        business_id=business_id,
        session_token=uuid.uuid4().hex,
        status="open",
        currency=payload.currency.upper(),
        customer_id=resolved_customer_id,
        payment_method=payload.payment_method,
        channel=payload.channel,
        note=payload.note,
        total_amount=to_money(total),
        success_redirect_url=payload.success_redirect_url,
        cancel_redirect_url=payload.cancel_redirect_url,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.expires_in_minutes),
    )
    db.add(checkout)

    for item in payload.items:
        unit_price = to_money(item.unit_price)
        line_total = to_money(unit_price * item.qty)
        db.add(
            CheckoutSessionItem(
                id=str(uuid.uuid4()),
                checkout_session_id=checkout.id,
                variant_id=item.variant_id,
                qty=item.qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    _init_provider_checkout(checkout=checkout, total_amount=float(to_money(total)))

    log_audit_event(
        db,
        business_id=business_id,
        actor_user_id=actor.id,
        action="checkout.session.create",
        target_type="checkout_session",
        target_id=checkout.id,
        metadata_json={
            "currency": checkout.currency,
            "payment_method": checkout.payment_method,
            "channel": checkout.channel,
            "total_amount": float(to_money(total)),
            "items_count": len(payload.items),
            "payment_provider": checkout.payment_provider,
        },
    )
    db.commit()
    return CheckoutSessionCreateOut(
        id=checkout.id,
        session_token=checkout.session_token,
        checkout_url=f"/checkout/{checkout.session_token}",
        status=checkout.status,
        payment_provider=checkout.payment_provider,
        payment_reference=checkout.payment_reference,
        payment_checkout_url=checkout.payment_checkout_url,
        total_amount=float(to_money(total)),
        expires_at=checkout.expires_at,
    )


@router.post(
    "/storefront/{slug}/session",
    response_model=CheckoutSessionCreateOut,
    summary="Create public checkout session from storefront product variant",
    responses=error_responses(400, 404, 422, 500),
)
def create_storefront_checkout_session(
    slug: str,
    payload: StorefrontCheckoutSessionCreateIn,
    db: Session = Depends(get_db),
):
    storefront = _public_storefront_or_404(db, slug=slug)
    checkout = _create_storefront_checkout_session(
        db,
        storefront=storefront,
        items=[(payload.variant_id, payload.qty)],
        audit_action="checkout.session.create_storefront",
        payment_method=payload.payment_method,
        channel=payload.channel,
        note=payload.note,
        success_redirect_url=payload.success_redirect_url,
        cancel_redirect_url=payload.cancel_redirect_url,
        expires_in_minutes=payload.expires_in_minutes,
    )
    db.commit()
    return CheckoutSessionCreateOut(
        id=checkout.id,
        session_token=checkout.session_token,
        checkout_url=f"/checkout/{checkout.session_token}",
        status=checkout.status,
        payment_provider=checkout.payment_provider,
        payment_reference=checkout.payment_reference,
        payment_checkout_url=checkout.payment_checkout_url,
        total_amount=float(to_money(total)),
        expires_at=checkout.expires_at,
    )


@router.post(
    "/storefront/{slug}/cart-session",
    response_model=CheckoutSessionCreateOut,
    summary="Create public checkout session from storefront cart",
    responses=error_responses(400, 404, 422, 500),
)
def create_storefront_cart_checkout_session(
    slug: str,
    payload: StorefrontCartSessionCreateIn,
    db: Session = Depends(get_db),
):
    storefront = _public_storefront_or_404(db, slug=slug)
    checkout = _create_storefront_checkout_session(
        db,
        storefront=storefront,
        items=[(item.variant_id, item.qty) for item in payload.items],
        audit_action="checkout.session.create_storefront_cart",
        payment_method=payload.payment_method,
        channel=payload.channel,
        note=payload.note,
        success_redirect_url=payload.success_redirect_url,
        cancel_redirect_url=payload.cancel_redirect_url,
        expires_in_minutes=payload.expires_in_minutes,
    )
    db.commit()
    return CheckoutSessionCreateOut(
        id=checkout.id,
        session_token=checkout.session_token,
        checkout_url=f"/checkout/{checkout.session_token}",
        status=checkout.status,
        payment_provider=checkout.payment_provider,
        payment_reference=checkout.payment_reference,
        payment_checkout_url=checkout.payment_checkout_url,
        total_amount=float(to_money(checkout.total_amount)),
        expires_at=checkout.expires_at,
    )


@management_router.get(
    "",
    response_model=CheckoutSessionListOut,
    summary="List checkout sessions",
    responses=error_responses(400, 401, 403, 422, 500),
)
def list_checkout_sessions(
    status: str | None = Query(default=None),
    payment_provider: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    normalized_status = _normalize_session_status(status)
    normalized_provider = payment_provider.strip().lower() if payment_provider and payment_provider.strip() else None

    count_stmt = select(func.count(CheckoutSession.id)).where(CheckoutSession.business_id == access.business.id)
    data_stmt = select(CheckoutSession).where(CheckoutSession.business_id == access.business.id)

    if normalized_status:
        count_stmt = count_stmt.where(CheckoutSession.status == normalized_status)
        data_stmt = data_stmt.where(CheckoutSession.status == normalized_status)
    if normalized_provider:
        count_stmt = count_stmt.where(CheckoutSession.payment_provider == normalized_provider)
        data_stmt = data_stmt.where(CheckoutSession.payment_provider == normalized_provider)
    if start_date:
        count_stmt = count_stmt.where(func.date(CheckoutSession.created_at) >= start_date)
        data_stmt = data_stmt.where(func.date(CheckoutSession.created_at) >= start_date)
    if end_date:
        count_stmt = count_stmt.where(func.date(CheckoutSession.created_at) <= end_date)
        data_stmt = data_stmt.where(func.date(CheckoutSession.created_at) <= end_date)

    total = int(db.execute(count_stmt).scalar_one())
    sessions = db.execute(
        data_stmt.order_by(CheckoutSession.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    changed = False
    for session in sessions:
        if _mark_session_expired_if_needed(session):
            changed = True
    if changed:
        db.commit()
        for session in sessions:
            db.refresh(session)

    order_ids = [session.order_id for session in sessions if session.order_id]
    order_rows = (
        db.execute(
            select(Order.id, Order.status, Order.sale_id).where(
                Order.business_id == access.business.id,
                Order.id.in_(order_ids),
            )
        ).all()
        if order_ids
        else []
    )
    order_lookup = {
        order_id: {"status": order_status, "sale_id": sale_id}
        for order_id, order_status, sale_id in order_rows
    }
    customer_name_map = get_customer_name_map(
        db,
        business_id=access.business.id,
        customer_ids=[session.customer_id for session in sessions],
    )
    items = [
        _checkout_out(
            db,
            session,
            order_lookup=order_lookup,
            customer_name_map=customer_name_map,
        )
        for session in sessions
    ]
    count = len(items)
    return CheckoutSessionListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        status=normalized_status,
        payment_provider=normalized_provider,
        start_date=start_date,
        end_date=end_date,
    )


@management_router.post(
    "/{checkout_session_id}/retry-payment",
    response_model=CheckoutSessionRetryPaymentOut,
    summary="Retry failed or pending checkout payment",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def retry_checkout_payment(
    checkout_session_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    checkout = _checkout_by_id_or_404(
        db,
        checkout_session_id=checkout_session_id,
        business_id=access.business.id,
    )
    if _mark_session_expired_if_needed(checkout):
        db.commit()
        db.refresh(checkout)

    if checkout.status not in {"payment_failed", "pending_payment", "open"}:
        raise HTTPException(status_code=400, detail=f"Cannot retry payment for status={checkout.status}")

    checkout.status = "pending_payment"
    checkout.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.checkout_retry_expiry_extension_minutes
    )
    _init_provider_checkout(checkout=checkout, total_amount=float(to_money(checkout.total_amount)))

    log_audit_event(
        db,
        business_id=checkout.business_id,
        actor_user_id=actor.id,
        action="checkout.payment.retry",
        target_type="checkout_session",
        target_id=checkout.id,
        metadata_json={
            "status": checkout.status,
            "payment_provider": checkout.payment_provider,
            "payment_reference": checkout.payment_reference,
        },
    )
    db.commit()
    return CheckoutSessionRetryPaymentOut(
        checkout_session_id=checkout.id,
        checkout_session_token=checkout.session_token,
        checkout_status=checkout.status,
        payment_provider=checkout.payment_provider,
        payment_reference=checkout.payment_reference or "",
        payment_checkout_url=checkout.payment_checkout_url,
        expires_at=checkout.expires_at,
    )


@management_router.get(
    "/payments-summary",
    response_model=CheckoutPaymentsSummaryOut,
    summary="Get payments operations summary",
    responses=error_responses(400, 401, 403, 422, 500),
)
def payments_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    stmt = select(CheckoutSession).where(CheckoutSession.business_id == access.business.id)
    if start_date:
        stmt = stmt.where(func.date(CheckoutSession.created_at) >= start_date)
    if end_date:
        stmt = stmt.where(func.date(CheckoutSession.created_at) <= end_date)

    sessions = db.execute(stmt).scalars().all()

    changed = False
    for session in sessions:
        if _mark_session_expired_if_needed(session):
            changed = True
    if changed:
        db.commit()
        for session in sessions:
            db.refresh(session)

    total_sessions = len(sessions)
    open_count = sum(1 for s in sessions if s.status == "open")
    pending_payment_count = sum(1 for s in sessions if s.status == "pending_payment")
    failed_count = sum(1 for s in sessions if s.status == "payment_failed")
    paid_count = sum(1 for s in sessions if s.status == "paid")
    expired_count = sum(1 for s in sessions if s.status == "expired")
    paid_amount_total = float(
        sum(to_money(s.total_amount) for s in sessions if s.status == "paid")
    )

    order_rows = db.execute(
        select(Order.id, Order.sale_id, Order.status).where(
            Order.business_id == access.business.id,
            Order.id.in_([s.order_id for s in sessions if s.order_id]),
        )
    ).all()
    order_map = {order_id: {"sale_id": sale_id, "status": order_status} for order_id, sale_id, order_status in order_rows}
    reconciled_count = 0
    for session in sessions:
        if session.status != "paid":
            continue
        order = order_map.get(session.order_id or "")
        if order and order["status"] == "paid" and order["sale_id"]:
            reconciled_count += 1
    unreconciled_count = max(paid_count - reconciled_count, 0)

    return CheckoutPaymentsSummaryOut(
        total_sessions=total_sessions,
        open_count=open_count,
        pending_payment_count=pending_payment_count,
        failed_count=failed_count,
        paid_count=paid_count,
        expired_count=expired_count,
        paid_amount_total=paid_amount_total,
        reconciled_count=reconciled_count,
        unreconciled_count=unreconciled_count,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/{session_token}",
    response_model=CheckoutSessionPublicOut,
    summary="Get public checkout session",
    responses=error_responses(404, 422, 500),
)
def get_checkout_session(
    session_token: str,
    db: Session = Depends(get_db),
):
    checkout = _checkout_by_token_or_404(db, session_token=session_token)
    if _mark_session_expired_if_needed(checkout):
        db.commit()
        db.refresh(checkout)

    customer_name_map = get_customer_name_map(
        db,
        business_id=checkout.business_id,
        customer_ids=[checkout.customer_id],
    )
    return CheckoutSessionPublicOut(
        session_token=checkout.session_token,
        status=checkout.status,
        currency=checkout.currency,
        customer_id=checkout.customer_id,
        customer_name=customer_name_map.get(checkout.customer_id or ""),
        payment_method=checkout.payment_method,
        channel=checkout.channel,
        note=checkout.note,
        total_amount=float(to_money(checkout.total_amount)),
        payment_provider=checkout.payment_provider,
        payment_reference=checkout.payment_reference,
        payment_checkout_url=checkout.payment_checkout_url,
        expires_at=checkout.expires_at,
        items=_checkout_public_items(db, checkout),
    )


@router.post(
    "/{session_token}/place-order",
    response_model=CheckoutSessionPlaceOrderOut,
    summary="Place order from checkout session",
    responses=error_responses(400, 404, 422, 500),
)
def place_order_from_checkout_session(
    session_token: str,
    payload: CheckoutSessionPlaceOrderIn,
    db: Session = Depends(get_db),
):
    checkout = _checkout_by_token_or_404(db, session_token=session_token)
    if _mark_session_expired_if_needed(checkout):
        db.commit()
        db.refresh(checkout)

    if checkout.status != "open":
        raise HTTPException(status_code=400, detail=f"Checkout session is not open (status={checkout.status})")

    resolved_customer_id = _resolve_or_create_checkout_customer_id(
        db,
        business_id=checkout.business_id,
        customer_id=payload.customer_id or checkout.customer_id,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
    )

    items = db.execute(
        select(CheckoutSessionItem).where(CheckoutSessionItem.checkout_session_id == checkout.id)
    ).scalars().all()
    if not items:
        raise HTTPException(status_code=400, detail="Checkout session has no items")

    order_id = str(uuid.uuid4())
    order = Order(
        id=order_id,
        business_id=checkout.business_id,
        customer_id=resolved_customer_id,
        payment_method=payload.payment_method or checkout.payment_method,
        channel=checkout.channel,
        status="pending",
        total_amount=to_money(checkout.total_amount),
        note=payload.note or checkout.note,
    )
    db.add(order)

    for item in items:
        db.add(
            OrderItem(
                id=str(uuid.uuid4()),
                order_id=order_id,
                variant_id=item.variant_id,
                qty=item.qty,
                unit_price=to_money(item.unit_price),
                line_total=to_money(item.line_total),
            )
        )

    checkout.status = "pending_payment"
    checkout.order_id = order_id
    checkout.customer_id = resolved_customer_id

    business = db.execute(select(Business).where(Business.id == checkout.business_id)).scalar_one()
    log_audit_event(
        db,
        business_id=checkout.business_id,
        actor_user_id=business.owner_user_id,
        action="checkout.session.place_order",
        target_type="checkout_session",
        target_id=checkout.id,
        metadata_json={
            "order_id": order_id,
            "checkout_status": checkout.status,
        },
    )
    db.commit()
    customer_name_map = get_customer_name_map(
        db,
        business_id=checkout.business_id,
        customer_ids=[resolved_customer_id],
    )
    return CheckoutSessionPlaceOrderOut(
        checkout_session_id=checkout.id,
        checkout_session_token=checkout.session_token,
        checkout_status=checkout.status,
        order_id=order_id,
        order_reference=build_display_reference("ORD", order_id),
        order_status="pending",
        customer_id=resolved_customer_id,
        customer_name=customer_name_map.get(resolved_customer_id or ""),
        total_amount=float(to_money(order.total_amount)),
    )


@webhooks_router.post(
    "/{provider}",
    response_model=CheckoutWebhookOut,
    summary="Process payment webhook callback",
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
async def process_payment_webhook(
    provider: str,
    payload: CheckoutWebhookEventIn,
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    signature = request.headers.get("X-Monidesk-Signature")
    _assert_webhook_signature(raw_body, signature)

    normalized_provider = provider.strip().lower()
    if not normalized_provider:
        raise HTTPException(status_code=400, detail="Provider is required")

    duplicate_event = db.execute(
        select(CheckoutWebhookEvent).where(CheckoutWebhookEvent.event_id == payload.event_id)
    ).scalar_one_or_none()
    if duplicate_event:
        checkout = db.execute(
            select(CheckoutSession).where(CheckoutSession.id == duplicate_event.checkout_session_id)
        ).scalar_one_or_none()
        return CheckoutWebhookOut(
            ok=True,
            provider=normalized_provider,
            checkout_session_id=checkout.id if checkout else None,
            checkout_session_status=checkout.status if checkout else None,
            order_id=checkout.order_id if checkout else None,
            order_reference=build_display_reference("ORD", checkout.order_id if checkout else None),
            duplicate=True,
        )

    checkout: CheckoutSession | None = None
    if payload.session_token:
        checkout = db.execute(
            select(CheckoutSession).where(CheckoutSession.session_token == payload.session_token)
        ).scalar_one_or_none()
    if not checkout and payload.payment_reference:
        checkout = db.execute(
            select(CheckoutSession).where(
                CheckoutSession.payment_reference == payload.payment_reference
            )
        ).scalar_one_or_none()

    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout session not found for webhook payload")

    db.add(
        CheckoutWebhookEvent(
            id=str(uuid.uuid4()),
            checkout_session_id=checkout.id,
            provider=normalized_provider,
            event_id=payload.event_id,
            event_type=payload.event_type,
            payload_json=payload.model_dump(mode="json"),
        )
    )

    normalized_event = payload.event_type.strip().lower()
    normalized_status = (payload.status or "").strip().lower()
    success_event = normalized_event in {"payment.succeeded", "charge.succeeded"} or normalized_status in {
        "success",
        "succeeded",
        "paid",
    }
    failed_event = normalized_event in {"payment.failed", "charge.failed"} or normalized_status in {
        "failed",
        "error",
    }

    order_id: str | None = None
    order_status: str | None = None
    if success_event:
        checkout.status = "paid"
        business = db.execute(select(Business).where(Business.id == checkout.business_id)).scalar_one()
        order_id, order_status = _sync_order_paid_from_checkout(
            db,
            checkout=checkout,
            actor_user_id=business.owner_user_id,
            webhook_event_id=payload.event_id,
        )
    elif failed_event:
        if checkout.status != "paid":
            checkout.status = "payment_failed"
    else:
        if checkout.status in {"open", "payment_failed"}:
            checkout.status = "pending_payment"

    db.commit()
    return CheckoutWebhookOut(
        ok=True,
        provider=normalized_provider,
        checkout_session_id=checkout.id,
        checkout_session_status=checkout.status,
        order_id=order_id or checkout.order_id,
        order_reference=build_display_reference("ORD", order_id or checkout.order_id),
        order_status=order_status,
        duplicate=False,
    )
