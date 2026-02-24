import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.config import settings
from app.core.deps import get_db
from app.core.money import ZERO_MONEY, to_money
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.product import ProductVariant
from app.models.sales import Sale, SaleItem
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.order import (
    ALLOWED_ORDER_STATUSES,
    OrderCreate,
    OrderCreateOut,
    OrderListOut,
    OrderOut,
    OrderStatusUpdateIn,
)
from app.services.audit_service import log_audit_event
from app.services.inventory_service import add_ledger_entry, get_variant_stock

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"paid", "cancelled"},
    "paid": {"processing", "fulfilled", "cancelled", "refunded"},
    "processing": {"fulfilled", "cancelled", "refunded"},
    "fulfilled": {"refunded"},
    "cancelled": set(),
    "refunded": set(),
}
ALLOWED_ORDER_CHANNELS = {"whatsapp", "instagram", "walk-in"}


def _normalize_order_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in ALLOWED_ORDER_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_ORDER_STATUSES))
        raise HTTPException(status_code=400, detail=f"Invalid order status. Allowed: {allowed}")
    return normalized


def _normalize_order_channel(channel: str) -> str:
    normalized = channel.strip().lower()
    if normalized not in ALLOWED_ORDER_CHANNELS:
        allowed = ", ".join(sorted(ALLOWED_ORDER_CHANNELS))
        raise HTTPException(status_code=400, detail=f"Invalid order channel. Allowed: {allowed}")
    return normalized


def _ensure_transition_allowed(current_status: str, next_status: str) -> None:
    if current_status == next_status:
        return
    allowed_next = ALLOWED_ORDER_TRANSITIONS.get(current_status, set())
    if next_status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition order from '{current_status}' to '{next_status}'",
        )


def _order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        customer_id=order.customer_id,
        payment_method=order.payment_method,
        channel=order.channel,
        status=order.status,
        total_amount=float(to_money(order.total_amount)),
        sale_id=order.sale_id,
        note=order.note,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _auto_cancel_note(timeout_minutes: int, existing_note: str | None) -> str:
    units = "minute" if timeout_minutes == 1 else "minutes"
    message = f"Auto-cancelled after {timeout_minutes} {units} without payment."
    if not existing_note or not existing_note.strip():
        return message[:255]
    return f"{existing_note.strip()} | {message}"[:255]


def _pending_timeout_minutes(access: BusinessAccess) -> int:
    configured = access.business.pending_order_timeout_minutes
    if configured and configured > 0:
        return configured
    return settings.orders_pending_timeout_minutes


def _auto_cancel_expired_pending_orders(
    db: Session,
    *,
    access: BusinessAccess,
    actor_user_id: str,
) -> int:
    timeout_minutes = _pending_timeout_minutes(access)
    cutoff_at = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    pending_orders = db.execute(
        select(Order).where(Order.business_id == access.business.id, Order.status == "pending")
    ).scalars().all()

    expired_orders = [order for order in pending_orders if _as_utc(order.created_at) <= cutoff_at]
    for order in expired_orders:
        order.status = "cancelled"
        order.note = _auto_cancel_note(timeout_minutes, order.note)
        log_audit_event(
            db,
            business_id=access.business.id,
            actor_user_id=actor_user_id,
            action="order.auto_cancel",
            target_type="order",
            target_id=order.id,
            metadata_json={
                "from_status": "pending",
                "to_status": "cancelled",
                "timeout_minutes": timeout_minutes,
                "cutoff_at": cutoff_at.isoformat(),
            },
        )
    return len(expired_orders)


def _variant_business_map(db: Session, variant_ids: list[str]) -> dict[str, str]:
    rows = db.execute(
        select(ProductVariant.id, ProductVariant.business_id).where(ProductVariant.id.in_(variant_ids))
    ).all()
    return {variant_id: business_id for variant_id, business_id in rows}


def _resolve_customer_id(
    db: Session,
    *,
    business_id: str,
    customer_id: str | None,
) -> str | None:
    if not customer_id:
        return None
    normalized_customer_id = customer_id.strip()
    if not normalized_customer_id:
        return None
    customer = db.execute(
        select(Customer.id).where(
            Customer.id == normalized_customer_id,
            Customer.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return normalized_customer_id


def _convert_order_to_sale(
    db: Session,
    *,
    order: Order,
    order_items: list[OrderItem],
    actor_user_id: str,
) -> str:
    if not order_items:
        raise HTTPException(status_code=400, detail="Order has no items")

    quantity_by_variant: dict[str, int] = {}
    for item in order_items:
        quantity_by_variant[item.variant_id] = quantity_by_variant.get(item.variant_id, 0) + item.qty

    variant_ids = list(quantity_by_variant.keys())
    business_by_variant = _variant_business_map(db, variant_ids)
    for variant_id in variant_ids:
        variant_business = business_by_variant.get(variant_id)
        if not variant_business:
            raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")
        if variant_business != order.business_id:
            raise HTTPException(status_code=403, detail="Order contains variant not in your business")

        stock = get_variant_stock(db, order.business_id, variant_id)
        if stock < quantity_by_variant[variant_id]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for variant {variant_id}",
            )

    sale_id = str(uuid.uuid4())
    sale = Sale(
        id=sale_id,
        business_id=order.business_id,
        payment_method=order.payment_method,
        channel=order.channel,
        note=order.note,
        total_amount=to_money(order.total_amount),
        kind="sale",
    )
    db.add(sale)

    for item in order_items:
        unit_price = to_money(item.unit_price)
        line_total = to_money(unit_price * item.qty)
        db.add(
            SaleItem(
                id=str(uuid.uuid4()),
                sale_id=sale_id,
                variant_id=item.variant_id,
                qty=item.qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
        add_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=order.business_id,
            variant_id=item.variant_id,
            qty_delta=-item.qty,
            reason="sale",
            reference_id=sale_id,
            note=order.note,
        )

    order.sale_id = sale_id

    log_audit_event(
        db,
        business_id=order.business_id,
        actor_user_id=actor_user_id,
        action="order.convert_to_sale",
        target_type="order",
        target_id=order.id,
        metadata_json={"sale_id": sale_id, "items_count": len(order_items)},
    )
    return sale_id


@router.post(
    "",
    response_model=OrderCreateOut,
    summary="Create order",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    biz = access.business
    resolved_customer_id = _resolve_customer_id(
        db,
        business_id=biz.id,
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
        if variant_business != biz.id:
            raise HTTPException(status_code=403, detail="Contains item not in your business")

    order_id = str(uuid.uuid4())
    order = Order(
        id=order_id,
        business_id=biz.id,
        customer_id=resolved_customer_id,
        payment_method=payload.payment_method,
        channel=payload.channel,
        status="pending",
        total_amount=to_money(total),
        note=payload.note,
    )
    db.add(order)

    for item in payload.items:
        unit_price = to_money(item.unit_price)
        line_total = to_money(unit_price * item.qty)
        db.add(
            OrderItem(
                id=str(uuid.uuid4()),
                order_id=order_id,
                variant_id=item.variant_id,
                qty=item.qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="order.create",
        target_type="order",
        target_id=order_id,
        metadata_json={
            "payment_method": payload.payment_method,
            "channel": payload.channel,
            "customer_id": resolved_customer_id,
            "items_count": len(payload.items),
            "total": float(to_money(total)),
        },
    )
    db.commit()
    return OrderCreateOut(id=order_id, total=float(to_money(total)), status="pending", sale_id=None)


@router.get(
    "",
    response_model=OrderListOut,
    summary="List orders",
    responses={**error_responses(400, 401, 403, 422, 500)},
)
def list_orders(
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    normalized_status = _normalize_order_status(status) if status else None
    normalized_channel = _normalize_order_channel(channel) if channel else None
    normalized_customer_id = customer_id.strip() if customer_id and customer_id.strip() else None

    cancelled_count = _auto_cancel_expired_pending_orders(
        db,
        access=access,
        actor_user_id=actor.id,
    )
    if cancelled_count > 0:
        db.commit()

    count_stmt = select(func.count(Order.id)).where(Order.business_id == access.business.id)
    data_stmt = select(Order).where(Order.business_id == access.business.id)

    if normalized_status:
        count_stmt = count_stmt.where(Order.status == normalized_status)
        data_stmt = data_stmt.where(Order.status == normalized_status)
    if normalized_channel:
        count_stmt = count_stmt.where(Order.channel == normalized_channel)
        data_stmt = data_stmt.where(Order.channel == normalized_channel)
    if normalized_customer_id:
        count_stmt = count_stmt.where(Order.customer_id == normalized_customer_id)
        data_stmt = data_stmt.where(Order.customer_id == normalized_customer_id)
    if start_date:
        count_stmt = count_stmt.where(func.date(Order.created_at) >= start_date)
        data_stmt = data_stmt.where(func.date(Order.created_at) >= start_date)
    if end_date:
        count_stmt = count_stmt.where(func.date(Order.created_at) <= end_date)
        data_stmt = data_stmt.where(func.date(Order.created_at) <= end_date)

    total_count = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        data_stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_order_out(row) for row in rows]
    count = len(items)

    return OrderListOut(
        pagination=PaginationMeta(
            total=total_count,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total_count,
        ),
        start_date=start_date,
        end_date=end_date,
        status=normalized_status,
        channel=normalized_channel,
        customer_id=normalized_customer_id,
        items=items,
    )


@router.patch(
    "/{order_id}/status",
    response_model=OrderOut,
    summary="Update order status",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def update_order_status(
    order_id: str,
    payload: OrderStatusUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    cancelled_count = _auto_cancel_expired_pending_orders(
        db,
        access=access,
        actor_user_id=actor.id,
    )
    if cancelled_count > 0:
        db.commit()

    order = db.execute(
        select(Order).where(Order.id == order_id, Order.business_id == access.business.id)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    next_status = _normalize_order_status(payload.status)
    current_status = _normalize_order_status(order.status)
    _ensure_transition_allowed(current_status, next_status)

    if payload.note is not None:
        order.note = payload.note
    if next_status != current_status:
        order.status = next_status

    converted_sale_id: str | None = None
    if next_status in {"paid", "fulfilled"} and order.sale_id is None:
        order_items = db.execute(select(OrderItem).where(OrderItem.order_id == order.id)).scalars().all()
        converted_sale_id = _convert_order_to_sale(
            db,
            order=order,
            order_items=order_items,
            actor_user_id=actor.id,
        )

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="order.status.update",
        target_type="order",
        target_id=order.id,
        metadata_json={
            "from_status": current_status,
            "to_status": next_status,
            "sale_id": order.sale_id,
            "converted_sale_id": converted_sale_id,
        },
    )
    db.commit()
    db.refresh(order)
    return _order_out(order)
