import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import ZERO_MONEY, to_money
from app.core.permissions import require_permission
from app.core.security_current import BusinessAccess, get_current_user
from app.models.order import Order, OrderItem
from app.models.pos import OfflineOrderSyncEvent, PosShiftSession
from app.models.product import ProductVariant
from app.models.user import User
from app.schemas.pos import (
    PosOfflineSyncIn,
    PosOfflineSyncOut,
    PosOfflineSyncResultOut,
    PosShiftCloseIn,
    PosShiftCurrentOut,
    PosShiftOpenIn,
    PosShiftOut,
)
from app.services.audit_service import log_audit_event
from app.services.inventory_service import add_ledger_entry, get_variant_stock

router = APIRouter(prefix="/pos", tags=["pos"])


def _shift_out(shift: PosShiftSession) -> PosShiftOut:
    return PosShiftOut(
        id=shift.id,
        status=shift.status,
        opening_cash=float(to_money(shift.opening_cash)),
        closing_cash=float(to_money(shift.closing_cash)) if shift.closing_cash is not None else None,
        expected_cash=float(to_money(shift.expected_cash)) if shift.expected_cash is not None else None,
        cash_difference=float(to_money(shift.cash_difference)) if shift.cash_difference is not None else None,
        opened_by_user_id=shift.opened_by_user_id,
        closed_by_user_id=shift.closed_by_user_id,
        note=shift.note,
        opened_at=shift.opened_at,
        closed_at=shift.closed_at,
    )


def _latest_open_shift(db: Session, *, business_id: str) -> PosShiftSession | None:
    # Defensive against legacy/dirty data where multiple open shifts may exist.
    return db.execute(
        select(PosShiftSession)
        .where(
            PosShiftSession.business_id == business_id,
            PosShiftSession.status == "open",
        )
        .order_by(PosShiftSession.opened_at.desc(), PosShiftSession.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


@router.post(
    "/shifts/open",
    response_model=PosShiftOut,
    summary="Open POS shift",
    responses=error_responses(400, 401, 403, 422, 500),
)
def open_shift(
    payload: PosShiftOpenIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("pos.shift.manage")),
    actor: User = Depends(get_current_user),
):
    active_shift = _latest_open_shift(db, business_id=access.business.id)
    if active_shift:
        raise HTTPException(status_code=400, detail="A POS shift is already open for this business")

    shift = PosShiftSession(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        opened_by_user_id=actor.id,
        status="open",
        opening_cash=to_money(payload.opening_cash),
        note=payload.note,
        opened_at=datetime.now(timezone.utc),
    )
    db.add(shift)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="pos.shift.open",
        target_type="pos_shift",
        target_id=shift.id,
        metadata_json={"opening_cash": float(to_money(payload.opening_cash))},
    )
    db.commit()
    db.refresh(shift)
    return _shift_out(shift)


@router.get(
    "/shifts/current",
    response_model=PosShiftCurrentOut,
    summary="Get current open POS shift",
    responses=error_responses(401, 403, 500),
)
def current_shift(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("pos.shift.manage")),
):
    try:
        shift = _latest_open_shift(db, business_id=access.business.id)
    except (OperationalError, ProgrammingError):
        # Keeps POS page usable if DB migrations for shift tables were skipped.
        db.rollback()
        return PosShiftCurrentOut(shift=None)
    return PosShiftCurrentOut(shift=_shift_out(shift) if shift else None)


@router.post(
    "/shifts/{shift_id}/close",
    response_model=PosShiftOut,
    summary="Close POS shift and reconcile cash",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def close_shift(
    shift_id: str,
    payload: PosShiftCloseIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("pos.shift.manage")),
    actor: User = Depends(get_current_user),
):
    shift = db.execute(
        select(PosShiftSession).where(
            PosShiftSession.id == shift_id,
            PosShiftSession.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift.status != "open":
        raise HTTPException(status_code=400, detail="Shift is already closed")

    cash_sales = db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.business_id == access.business.id,
            Order.payment_method == "cash",
            func.date(Order.created_at) >= shift.opened_at.date(),
            Order.status.in_(["pending", "paid", "processing", "fulfilled"]),
        )
    ).scalar_one()
    expected_cash = to_money(to_money(shift.opening_cash) + to_money(cash_sales or 0))
    closing_cash = to_money(payload.closing_cash)
    difference = to_money(closing_cash - expected_cash)

    shift.status = "closed"
    shift.closed_by_user_id = actor.id
    shift.closed_at = datetime.now(timezone.utc)
    shift.closing_cash = closing_cash
    shift.expected_cash = expected_cash
    shift.cash_difference = difference
    shift.note = payload.note or shift.note

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="pos.shift.close",
        target_type="pos_shift",
        target_id=shift.id,
        metadata_json={
            "closing_cash": float(closing_cash),
            "expected_cash": float(expected_cash),
            "cash_difference": float(difference),
        },
    )
    db.commit()
    db.refresh(shift)
    return _shift_out(shift)


@router.post(
    "/offline-orders/sync",
    response_model=PosOfflineSyncOut,
    summary="Sync offline POS orders with conflict resolution",
    responses=error_responses(400, 401, 403, 422, 500),
)
def sync_offline_orders(
    payload: PosOfflineSyncIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("pos.offline.sync")),
    actor: User = Depends(get_current_user),
):
    processed = 0
    created = 0
    conflicted = 0
    duplicate = 0
    results: list[PosOfflineSyncResultOut] = []

    for offline_order in payload.orders:
        processed += 1
        existing = db.execute(
            select(OfflineOrderSyncEvent).where(
                OfflineOrderSyncEvent.business_id == access.business.id,
                OfflineOrderSyncEvent.client_event_id == offline_order.client_event_id,
            )
        ).scalar_one_or_none()
        if existing:
            duplicate += 1
            results.append(
                PosOfflineSyncResultOut(
                    client_event_id=offline_order.client_event_id,
                    status="duplicate",
                    order_id=existing.order_id,
                    conflict_code=existing.conflict_code,
                    note="Already processed",
                )
            )
            continue

        normalized_items: list[tuple[str, int, object]] = []
        validation_conflict: str | None = None
        for item in offline_order.items:
            variant = db.execute(
                select(ProductVariant).where(
                    ProductVariant.id == item.variant_id,
                    ProductVariant.business_id == access.business.id,
                )
            ).scalar_one_or_none()
            if not variant:
                validation_conflict = "variant_not_found"
                break

            available = get_variant_stock(db, access.business.id, item.variant_id)
            effective_qty = int(item.qty)
            if available < effective_qty:
                if payload.conflict_policy == "adjust_to_available" and available > 0:
                    effective_qty = available
                else:
                    validation_conflict = "insufficient_stock"
                    break
            if effective_qty <= 0:
                validation_conflict = "insufficient_stock"
                break
            normalized_items.append((item.variant_id, effective_qty, item.unit_price))

        if validation_conflict:
            conflicted += 1
            sync_event = OfflineOrderSyncEvent(
                id=str(uuid.uuid4()),
                business_id=access.business.id,
                client_event_id=offline_order.client_event_id,
                order_id=None,
                status="conflict",
                conflict_code=validation_conflict,
                details_json={"policy": payload.conflict_policy},
            )
            db.add(sync_event)
            results.append(
                PosOfflineSyncResultOut(
                    client_event_id=offline_order.client_event_id,
                    status="conflict",
                    conflict_code=validation_conflict,
                    note="Order could not be synced due to stock conflict",
                )
            )
            continue

        order_total = ZERO_MONEY
        for _variant_id, qty, unit_price in normalized_items:
            order_total = to_money(order_total + to_money(unit_price) * qty)

        order = Order(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            customer_id=offline_order.customer_id,
            payment_method=offline_order.payment_method,
            channel=offline_order.channel,
            status="pending",
            total_amount=order_total,
            note=offline_order.note,
        )
        if offline_order.created_at:
            order.created_at = offline_order.created_at
        db.add(order)
        db.flush()

        for variant_id, qty, unit_price in normalized_items:
            line_total = to_money(to_money(unit_price) * qty)
            db.add(
                OrderItem(
                    id=str(uuid.uuid4()),
                    order_id=order.id,
                    variant_id=variant_id,
                    qty=qty,
                    unit_price=to_money(unit_price),
                    line_total=line_total,
                )
            )
            add_ledger_entry(
                db,
                ledger_id=str(uuid.uuid4()),
                business_id=access.business.id,
                variant_id=variant_id,
                qty_delta=-qty,
                reason="offline_order_sync",
                reference_id=order.id,
                note=offline_order.note,
            )

        db.add(
            OfflineOrderSyncEvent(
                id=str(uuid.uuid4()),
                business_id=access.business.id,
                client_event_id=offline_order.client_event_id,
                order_id=order.id,
                status="created",
                conflict_code=None,
                details_json={"policy": payload.conflict_policy},
            )
        )
        created += 1
        results.append(
            PosOfflineSyncResultOut(
                client_event_id=offline_order.client_event_id,
                status="created",
                order_id=order.id,
                note=f"Synced order total {float(order_total):.2f}",
            )
        )

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="pos.offline_orders.sync",
        target_type="offline_order_sync",
        target_id=None,
        metadata_json={
            "processed": processed,
            "created": created,
            "conflicted": conflicted,
            "duplicate": duplicate,
            "policy": payload.conflict_policy,
        },
    )
    db.commit()
    return PosOfflineSyncOut(
        processed=processed,
        created=created,
        conflicted=conflicted,
        duplicate=duplicate,
        results=results,
    )
