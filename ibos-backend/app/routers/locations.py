import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.business_membership import BusinessMembership
from app.models.location import (
    Location,
    LocationInventoryLedger,
    LocationMembershipScope,
    OrderLocationAllocation,
    StockTransfer,
    StockTransferItem,
)
from app.models.order import Order, OrderItem
from app.models.product import ProductVariant
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.location import (
    LocationCreateIn,
    LocationListOut,
    LocationLowStockItemOut,
    LocationLowStockListOut,
    LocationMembershipScopeListOut,
    LocationMembershipScopeOut,
    LocationMembershipScopeUpsertIn,
    LocationOut,
    LocationStockAdjustIn,
    LocationStockInIn,
    LocationStockOverviewOut,
    LocationUpdateIn,
    LocationVariantStockOut,
    OrderLocationAllocationIn,
    OrderLocationAllocationOut,
    StockTransferCreateIn,
    StockTransferItemOut,
    StockTransferListOut,
    StockTransferOut,
)
from app.services.audit_service import log_audit_event
from app.services.location_inventory_service import (
    add_location_ledger_entry,
    get_location_variant_stock,
)

router = APIRouter(prefix="/locations", tags=["locations"])


def _location_in_business_or_404(db: Session, *, business_id: str, location_id: str) -> Location:
    location = db.execute(
        select(Location).where(Location.id == location_id, Location.business_id == business_id)
    ).scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


def _variant_in_business_or_404(db: Session, *, business_id: str, variant_id: str) -> ProductVariant:
    variant = db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


def _location_out(location: Location) -> LocationOut:
    return LocationOut(
        id=location.id,
        name=location.name,
        code=location.code,
        is_active=location.is_active,
        created_at=location.created_at,
        updated_at=location.updated_at,
    )


def _transfer_out(db: Session, transfer: StockTransfer) -> StockTransferOut:
    items = db.execute(
        select(StockTransferItem).where(StockTransferItem.stock_transfer_id == transfer.id)
    ).scalars().all()
    return StockTransferOut(
        id=transfer.id,
        from_location_id=transfer.from_location_id,
        to_location_id=transfer.to_location_id,
        status=transfer.status,
        note=transfer.note,
        created_at=transfer.created_at,
        items=[StockTransferItemOut(variant_id=item.variant_id, qty=item.qty) for item in items],
    )


@router.post(
    "",
    response_model=LocationOut,
    summary="Create location",
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
def create_location(
    payload: LocationCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    normalized_code = payload.code.strip().upper()
    exists = db.execute(
        select(Location.id).where(
            Location.business_id == access.business.id,
            func.upper(Location.code) == normalized_code,
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Location code already exists")

    location = Location(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name.strip(),
        code=normalized_code,
        is_active=True,
    )
    db.add(location)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.create",
        target_type="location",
        target_id=location.id,
        metadata_json={"name": location.name, "code": location.code},
    )
    db.commit()
    db.refresh(location)
    return _location_out(location)


@router.get(
    "",
    response_model=LocationListOut,
    summary="List locations",
    responses=error_responses(401, 403, 422, 500),
)
def list_locations(
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(Location.id)).where(Location.business_id == access.business.id)
    stmt = select(Location).where(Location.business_id == access.business.id)
    if not include_inactive:
        count_stmt = count_stmt.where(Location.is_active.is_(True))
        stmt = stmt.where(Location.is_active.is_(True))

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(stmt.order_by(Location.created_at.asc()).offset(offset).limit(limit)).scalars().all()
    items = [_location_out(row) for row in rows]
    count = len(items)
    return LocationListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )


@router.patch(
    "/{location_id}",
    response_model=LocationOut,
    summary="Update location",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def update_location(
    location_id: str,
    payload: LocationUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    location = _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    if payload.name is not None:
        location.name = payload.name.strip()
    if payload.is_active is not None:
        location.is_active = payload.is_active

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.update",
        target_type="location",
        target_id=location.id,
        metadata_json={"name": location.name, "is_active": location.is_active},
    )
    db.commit()
    db.refresh(location)
    return _location_out(location)


@router.post(
    "/{location_id}/deactivate",
    response_model=LocationOut,
    summary="Deactivate location",
    responses=error_responses(401, 403, 404, 500),
)
def deactivate_location(
    location_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    location = _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    if not location.is_active:
        return _location_out(location)

    location.is_active = False
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.deactivate",
        target_type="location",
        target_id=location.id,
        metadata_json={"name": location.name, "is_active": location.is_active},
    )
    db.commit()
    db.refresh(location)
    return _location_out(location)


@router.post(
    "/{location_id}/activate",
    response_model=LocationOut,
    summary="Activate location",
    responses=error_responses(401, 403, 404, 500),
)
def activate_location(
    location_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    location = _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    if location.is_active:
        return _location_out(location)

    location.is_active = True
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.activate",
        target_type="location",
        target_id=location.id,
        metadata_json={"name": location.name, "is_active": location.is_active},
    )
    db.commit()
    db.refresh(location)
    return _location_out(location)


@router.put(
    "/{location_id}/membership-scopes/{membership_id}",
    response_model=LocationMembershipScopeOut,
    summary="Set location membership scope",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def upsert_location_membership_scope(
    location_id: str,
    membership_id: str,
    payload: LocationMembershipScopeUpsertIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    membership = db.execute(
        select(BusinessMembership).where(
            BusinessMembership.id == membership_id,
            BusinessMembership.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    scope = db.execute(
        select(LocationMembershipScope).where(
            LocationMembershipScope.location_id == location_id,
            LocationMembershipScope.membership_id == membership_id,
        )
    ).scalar_one_or_none()
    if not scope:
        scope = LocationMembershipScope(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            location_id=location_id,
            membership_id=membership_id,
            can_manage_inventory=payload.can_manage_inventory,
        )
        db.add(scope)
    else:
        scope.can_manage_inventory = payload.can_manage_inventory

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.membership_scope.upsert",
        target_type="location_membership_scope",
        target_id=scope.id,
        metadata_json={
            "location_id": location_id,
            "membership_id": membership_id,
            "can_manage_inventory": scope.can_manage_inventory,
        },
    )
    db.commit()
    db.refresh(scope)
    return LocationMembershipScopeOut(
        id=scope.id,
        membership_id=scope.membership_id,
        location_id=scope.location_id,
        can_manage_inventory=scope.can_manage_inventory,
        created_at=scope.created_at,
    )


@router.get(
    "/{location_id}/membership-scopes",
    response_model=LocationMembershipScopeListOut,
    summary="List location membership scopes",
    responses=error_responses(401, 403, 404, 500),
)
def list_location_membership_scopes(
    location_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    scopes = db.execute(
        select(LocationMembershipScope).where(
            LocationMembershipScope.location_id == location_id,
            LocationMembershipScope.business_id == access.business.id,
        )
    ).scalars().all()
    return LocationMembershipScopeListOut(
        items=[
            LocationMembershipScopeOut(
                id=scope.id,
                membership_id=scope.membership_id,
                location_id=scope.location_id,
                can_manage_inventory=scope.can_manage_inventory,
                created_at=scope.created_at,
            )
            for scope in scopes
        ]
    )


@router.post(
    "/{location_id}/stock-in",
    response_model=LocationVariantStockOut,
    summary="Add stock to a location",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def stock_in_location(
    location_id: str,
    payload: LocationStockInIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    _variant_in_business_or_404(db, business_id=access.business.id, variant_id=payload.variant_id)

    add_location_ledger_entry(
        db,
        ledger_id=str(uuid.uuid4()),
        business_id=access.business.id,
        location_id=location_id,
        variant_id=payload.variant_id,
        qty_delta=payload.qty,
        reason="stock_in",
        note=payload.note,
    )
    db.flush()
    stock = get_location_variant_stock(
        db,
        business_id=access.business.id,
        location_id=location_id,
        variant_id=payload.variant_id,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.inventory.stock_in",
        target_type="location",
        target_id=location_id,
        metadata_json={"variant_id": payload.variant_id, "qty": payload.qty, "stock_after": stock},
    )
    db.commit()
    return LocationVariantStockOut(location_id=location_id, variant_id=payload.variant_id, stock=stock)


@router.post(
    "/{location_id}/adjust",
    response_model=LocationVariantStockOut,
    summary="Adjust stock in a location",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def adjust_location_stock(
    location_id: str,
    payload: LocationStockAdjustIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    _variant_in_business_or_404(db, business_id=access.business.id, variant_id=payload.variant_id)

    current_stock = get_location_variant_stock(
        db,
        business_id=access.business.id,
        location_id=location_id,
        variant_id=payload.variant_id,
    )
    if payload.qty_delta < 0 and current_stock < abs(payload.qty_delta):
        raise HTTPException(status_code=400, detail="Insufficient stock for adjustment")

    add_location_ledger_entry(
        db,
        ledger_id=str(uuid.uuid4()),
        business_id=access.business.id,
        location_id=location_id,
        variant_id=payload.variant_id,
        qty_delta=payload.qty_delta,
        reason="adjustment",
        note=f"{payload.reason}: {payload.note}" if payload.note else payload.reason,
    )
    db.flush()
    stock_after = get_location_variant_stock(
        db,
        business_id=access.business.id,
        location_id=location_id,
        variant_id=payload.variant_id,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.inventory.adjust",
        target_type="location",
        target_id=location_id,
        metadata_json={
            "variant_id": payload.variant_id,
            "qty_delta": payload.qty_delta,
            "reason": payload.reason,
            "stock_after": stock_after,
        },
    )
    db.commit()
    return LocationVariantStockOut(location_id=location_id, variant_id=payload.variant_id, stock=stock_after)


@router.get(
    "/{location_id}/stock/{variant_id}",
    response_model=LocationVariantStockOut,
    summary="Get location stock for variant",
    responses=error_responses(401, 403, 404, 500),
)
def get_location_stock(
    location_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _location_in_business_or_404(db, business_id=access.business.id, location_id=location_id)
    _variant_in_business_or_404(db, business_id=access.business.id, variant_id=variant_id)
    stock = get_location_variant_stock(
        db,
        business_id=access.business.id,
        location_id=location_id,
        variant_id=variant_id,
    )
    return LocationVariantStockOut(location_id=location_id, variant_id=variant_id, stock=stock)


@router.get(
    "/stock-overview/{variant_id}",
    response_model=LocationStockOverviewOut,
    summary="Get variant stock by location",
    responses=error_responses(401, 403, 404, 500),
)
def get_location_stock_overview(
    variant_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _variant_in_business_or_404(db, business_id=access.business.id, variant_id=variant_id)
    locations = db.execute(
        select(Location).where(
            Location.business_id == access.business.id,
            Location.is_active.is_(True),
        )
    ).scalars().all()
    by_location = [
        LocationVariantStockOut(
            location_id=location.id,
            variant_id=variant_id,
            stock=get_location_variant_stock(
                db,
                business_id=access.business.id,
                location_id=location.id,
                variant_id=variant_id,
            ),
        )
        for location in locations
    ]
    return LocationStockOverviewOut(variant_id=variant_id, by_location=by_location)


@router.post(
    "/transfers",
    response_model=StockTransferOut,
    summary="Create inter-location stock transfer",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_stock_transfer(
    payload: StockTransferCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(status_code=400, detail="Source and destination locations must be different")

    _location_in_business_or_404(db, business_id=access.business.id, location_id=payload.from_location_id)
    _location_in_business_or_404(db, business_id=access.business.id, location_id=payload.to_location_id)

    for item in payload.items:
        _variant_in_business_or_404(db, business_id=access.business.id, variant_id=item.variant_id)
        source_stock = get_location_variant_stock(
            db,
            business_id=access.business.id,
            location_id=payload.from_location_id,
            variant_id=item.variant_id,
        )
        if source_stock < item.qty:
            raise HTTPException(status_code=400, detail=f"Insufficient source stock for variant {item.variant_id}")

    transfer = StockTransfer(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        from_location_id=payload.from_location_id,
        to_location_id=payload.to_location_id,
        created_by_user_id=actor.id,
        status="completed",
        note=payload.note,
    )
    db.add(transfer)

    for item in payload.items:
        db.add(
            StockTransferItem(
                id=str(uuid.uuid4()),
                stock_transfer_id=transfer.id,
                variant_id=item.variant_id,
                qty=item.qty,
            )
        )
        add_location_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=access.business.id,
            location_id=payload.from_location_id,
            variant_id=item.variant_id,
            qty_delta=-item.qty,
            reason="transfer_out",
            reference_id=transfer.id,
            note=payload.note,
        )
        add_location_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=access.business.id,
            location_id=payload.to_location_id,
            variant_id=item.variant_id,
            qty_delta=item.qty,
            reason="transfer_in",
            reference_id=transfer.id,
            note=payload.note,
        )

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.transfer.create",
        target_type="stock_transfer",
        target_id=transfer.id,
        metadata_json={
            "from_location_id": transfer.from_location_id,
            "to_location_id": transfer.to_location_id,
            "items_count": len(payload.items),
        },
    )
    db.commit()
    db.refresh(transfer)
    return _transfer_out(db, transfer)


@router.get(
    "/transfers",
    response_model=StockTransferListOut,
    summary="List stock transfers",
    responses=error_responses(401, 403, 422, 500),
)
def list_stock_transfers(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(StockTransfer.id)).where(StockTransfer.business_id == access.business.id)
    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        select(StockTransfer)
        .where(StockTransfer.business_id == access.business.id)
        .order_by(StockTransfer.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    items = [_transfer_out(db, row) for row in rows]
    count = len(items)
    return StockTransferListOut(
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
    "/low-stock",
    response_model=LocationLowStockListOut,
    summary="List low-stock variants by location",
    responses=error_responses(401, 403, 422, 500),
)
def list_location_low_stock(
    location_id: str | None = Query(default=None),
    threshold: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    locations_query = select(Location.id).where(
        Location.business_id == access.business.id,
        Location.is_active.is_(True),
    )
    if location_id:
        locations_query = locations_query.where(Location.id == location_id)
    location_ids = db.execute(locations_query).scalars().all()
    if not location_ids:
        return LocationLowStockListOut(
            items=[],
            pagination=PaginationMeta(total=0, limit=limit, offset=offset, count=0, has_next=False),
        )

    variant_rows = db.execute(
        select(ProductVariant.id, ProductVariant.reorder_level).where(ProductVariant.business_id == access.business.id)
    ).all()
    if not variant_rows:
        return LocationLowStockListOut(
            items=[],
            pagination=PaginationMeta(total=0, limit=limit, offset=offset, count=0, has_next=False),
        )

    variant_ids = [variant_id for variant_id, _reorder_level in variant_rows]
    stock_rows = db.execute(
        select(
            LocationInventoryLedger.location_id,
            LocationInventoryLedger.variant_id,
            func.coalesce(func.sum(LocationInventoryLedger.qty_delta), 0),
        )
        .where(
            LocationInventoryLedger.business_id == access.business.id,
            LocationInventoryLedger.location_id.in_(location_ids),
            LocationInventoryLedger.variant_id.in_(variant_ids),
        )
        .group_by(LocationInventoryLedger.location_id, LocationInventoryLedger.variant_id)
    ).all()
    stock_by_pair = {
        (row_location_id, row_variant_id): int(stock_qty)
        for row_location_id, row_variant_id, stock_qty in stock_rows
    }

    items: list[LocationLowStockItemOut] = []
    for location_row_id in location_ids:
        for variant_id, reorder_level in variant_rows:
            stock = stock_by_pair.get((location_row_id, variant_id), 0)
            threshold_value = reorder_level if reorder_level > 0 else threshold
            if stock <= threshold_value:
                items.append(
                    LocationLowStockItemOut(
                        location_id=location_row_id,
                        variant_id=variant_id,
                        reorder_level=threshold_value,
                        stock=stock,
                    )
                )
    total = len(items)
    paged = items[offset : offset + limit]
    count = len(paged)
    return LocationLowStockListOut(
        items=paged,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )


@router.post(
    "/order-allocations",
    response_model=OrderLocationAllocationOut,
    summary="Allocate order to location and reserve stock",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def allocate_order_to_location(
    payload: OrderLocationAllocationIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    order = db.execute(
        select(Order).where(Order.id == payload.order_id, Order.business_id == access.business.id)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    _location_in_business_or_404(db, business_id=access.business.id, location_id=payload.location_id)
    existing = db.execute(
        select(OrderLocationAllocation).where(
            OrderLocationAllocation.order_id == payload.order_id,
            OrderLocationAllocation.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Order already allocated to a location")

    order_items = db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).scalars().all()
    if not order_items:
        raise HTTPException(status_code=400, detail="Order has no items")

    qty_by_variant: dict[str, int] = {}
    for item in order_items:
        qty_by_variant[item.variant_id] = qty_by_variant.get(item.variant_id, 0) + item.qty

    for variant_id, qty in qty_by_variant.items():
        stock = get_location_variant_stock(
            db,
            business_id=access.business.id,
            location_id=payload.location_id,
            variant_id=variant_id,
        )
        if stock < qty:
            raise HTTPException(status_code=400, detail=f"Insufficient location stock for variant {variant_id}")

    allocation = OrderLocationAllocation(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        order_id=order.id,
        location_id=payload.location_id,
        allocated_by_user_id=actor.id,
    )
    db.add(allocation)

    for variant_id, qty in qty_by_variant.items():
        add_location_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=access.business.id,
            location_id=payload.location_id,
            variant_id=variant_id,
            qty_delta=-qty,
            reason="order_allocation_reserve",
            reference_id=order.id,
            note="Order location allocation reserve",
        )

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="location.order.allocate",
        target_type="order_location_allocation",
        target_id=allocation.id,
        metadata_json={
            "order_id": allocation.order_id,
            "location_id": allocation.location_id,
            "items_count": len(qty_by_variant),
        },
    )
    db.commit()
    db.refresh(allocation)
    return OrderLocationAllocationOut(
        id=allocation.id,
        order_id=allocation.order_id,
        location_id=allocation.location_id,
        allocated_at=allocation.allocated_at,
    )
