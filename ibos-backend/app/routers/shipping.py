import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import to_money
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.checkout import CheckoutSession
from app.models.order import Order
from app.models.shipping import (
    CheckoutShippingSelection,
    Shipment,
    ShipmentTrackingEvent,
    ShippingProfile,
    ShippingServiceRule,
    ShippingZone,
)
from app.models.user import User
from app.routers.orders import _ensure_transition_allowed, _normalize_order_status
from app.schemas.common import PaginationMeta
from app.schemas.shipping import (
    ShipmentCreateIn,
    ShipmentListOut,
    ShipmentOut,
    ShipmentTrackingEventOut,
    ShipmentTrackingSyncOut,
    ShippingQuoteIn,
    ShippingQuoteOptionOut,
    ShippingQuoteOut,
    ShippingRateSelectIn,
    ShippingRateSelectionOut,
    ShippingServiceRuleOut,
    ShippingSettingsOut,
    ShippingSettingsUpsertIn,
    ShippingZoneOut,
)
from app.services.audit_service import log_audit_event
from app.services.carrier_provider import (
    ShippingLabelRequest,
    ShippingQuoteRequest,
    get_carrier_provider,
)

router = APIRouter(prefix="/shipping", tags=["shipping"])


def _shipping_profile_for_business(db: Session, *, business_id: str) -> ShippingProfile | None:
    return db.execute(
        select(ShippingProfile).where(ShippingProfile.business_id == business_id)
    ).scalar_one_or_none()


def _checkout_by_token_or_404(db: Session, *, session_token: str) -> CheckoutSession:
    checkout = db.execute(
        select(CheckoutSession).where(CheckoutSession.session_token == session_token)
    ).scalar_one_or_none()
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    return checkout


def _shipment_by_id_or_404(db: Session, *, shipment_id: str, business_id: str) -> Shipment:
    shipment = db.execute(
        select(Shipment).where(Shipment.id == shipment_id, Shipment.business_id == business_id)
    ).scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


def _shipping_settings_out(db: Session, *, profile: ShippingProfile) -> ShippingSettingsOut:
    zones = db.execute(
        select(ShippingZone).where(ShippingZone.profile_id == profile.id).order_by(ShippingZone.created_at.asc())
    ).scalars().all()
    rules = db.execute(
        select(ShippingServiceRule).where(ShippingServiceRule.profile_id == profile.id).order_by(ShippingServiceRule.created_at.asc())
    ).scalars().all()
    zone_name_by_id = {zone.id: zone.zone_name for zone in zones}

    return ShippingSettingsOut(
        profile_id=profile.id,
        default_origin_country=profile.default_origin_country,
        default_origin_state=profile.default_origin_state,
        default_origin_city=profile.default_origin_city,
        default_origin_postal_code=profile.default_origin_postal_code,
        handling_fee=float(to_money(profile.handling_fee)),
        currency=profile.currency,
        zones=[
            ShippingZoneOut(
                id=zone.id,
                zone_name=zone.zone_name,
                country=zone.country,
                state=zone.state,
                city=zone.city,
                postal_code_prefix=zone.postal_code_prefix,
                is_active=zone.is_active,
            )
            for zone in zones
        ],
        service_rules=[
            ShippingServiceRuleOut(
                id=rule.id,
                provider=rule.provider,
                service_code=rule.service_code,
                service_name=rule.service_name,
                zone_name=zone_name_by_id.get(rule.zone_id),
                base_rate=float(to_money(rule.base_rate)),
                per_kg_rate=float(to_money(rule.per_kg_rate)),
                min_eta_days=rule.min_eta_days,
                max_eta_days=rule.max_eta_days,
                is_active=rule.is_active,
            )
            for rule in rules
        ],
        updated_at=profile.updated_at,
    )


def _resolve_zone_for_destination(
    *,
    zones: list[ShippingZone],
    destination_country: str,
    destination_state: str | None,
    destination_city: str | None,
    destination_postal_code: str | None,
) -> ShippingZone | None:
    normalized_country = destination_country.strip().lower()
    normalized_state = destination_state.strip().lower() if destination_state else None
    normalized_city = destination_city.strip().lower() if destination_city else None
    normalized_postal = destination_postal_code.strip().lower() if destination_postal_code else None

    candidates: list[tuple[int, ShippingZone]] = []
    for zone in zones:
        if not zone.is_active:
            continue
        if zone.country.strip().lower() != normalized_country:
            continue
        score = 1
        if zone.state and normalized_state and zone.state.strip().lower() == normalized_state:
            score += 2
        if zone.city and normalized_city and zone.city.strip().lower() == normalized_city:
            score += 2
        if zone.postal_code_prefix and normalized_postal and normalized_postal.startswith(zone.postal_code_prefix.strip().lower()):
            score += 3
        candidates.append((score, zone))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _shipment_out(db: Session, shipment: Shipment) -> ShipmentOut:
    tracking_events = db.execute(
        select(ShipmentTrackingEvent).where(ShipmentTrackingEvent.shipment_id == shipment.id).order_by(ShipmentTrackingEvent.event_time.desc())
    ).scalars().all()
    return ShipmentOut(
        id=shipment.id,
        order_id=shipment.order_id,
        checkout_session_id=shipment.checkout_session_id,
        provider=shipment.provider,
        service_code=shipment.service_code,
        service_name=shipment.service_name,
        status=shipment.status,
        shipping_cost=float(to_money(shipment.shipping_cost)),
        currency=shipment.currency,
        tracking_number=shipment.tracking_number,
        label_url=shipment.label_url,
        recipient_name=shipment.recipient_name,
        recipient_phone=shipment.recipient_phone,
        address_line1=shipment.address_line1,
        address_line2=shipment.address_line2,
        city=shipment.city,
        state=shipment.state,
        country=shipment.country,
        postal_code=shipment.postal_code,
        shipped_at=shipment.shipped_at,
        delivered_at=shipment.delivered_at,
        created_at=shipment.created_at,
        updated_at=shipment.updated_at,
        tracking_events=[
            ShipmentTrackingEventOut(
                id=item.id,
                status=item.status,
                description=item.description,
                event_time=item.event_time,
                created_at=item.created_at,
            )
            for item in tracking_events
        ],
    )


@router.put(
    "/settings",
    response_model=ShippingSettingsOut,
    summary="Create or update shipping settings",
    responses=error_responses(400, 401, 403, 422, 500),
)
def upsert_shipping_settings(
    payload: ShippingSettingsUpsertIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    profile = _shipping_profile_for_business(db, business_id=access.business.id)
    if not profile:
        profile = ShippingProfile(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
        )
        db.add(profile)
        db.flush()

    profile.default_origin_country = payload.default_origin_country.upper()
    profile.default_origin_state = payload.default_origin_state
    profile.default_origin_city = payload.default_origin_city
    profile.default_origin_postal_code = payload.default_origin_postal_code
    profile.handling_fee = to_money(payload.handling_fee)
    profile.currency = payload.currency.upper()

    db.execute(delete(ShippingServiceRule).where(ShippingServiceRule.profile_id == profile.id))
    db.execute(delete(ShippingZone).where(ShippingZone.profile_id == profile.id))
    db.flush()

    zone_id_by_name: dict[str, str] = {}
    for zone in payload.zones:
        zone_id = str(uuid.uuid4())
        db.add(
            ShippingZone(
                id=zone_id,
                profile_id=profile.id,
                zone_name=zone.zone_name,
                country=zone.country.upper(),
                state=zone.state,
                city=zone.city,
                postal_code_prefix=zone.postal_code_prefix,
                is_active=zone.is_active,
            )
        )
        zone_id_by_name[zone.zone_name.strip().lower()] = zone_id

    for rule in payload.service_rules:
        zone_id = None
        if rule.zone_name:
            zone_id = zone_id_by_name.get(rule.zone_name.strip().lower())
            if not zone_id:
                raise HTTPException(status_code=400, detail=f"Unknown zone_name in service rule: {rule.zone_name}")
        db.add(
            ShippingServiceRule(
                id=str(uuid.uuid4()),
                profile_id=profile.id,
                zone_id=zone_id,
                provider=rule.provider.lower(),
                service_code=rule.service_code,
                service_name=rule.service_name,
                base_rate=to_money(rule.base_rate),
                per_kg_rate=to_money(rule.per_kg_rate),
                min_eta_days=rule.min_eta_days,
                max_eta_days=rule.max_eta_days,
                is_active=rule.is_active,
            )
        )

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="shipping.settings.upsert",
        target_type="shipping_profile",
        target_id=profile.id,
        metadata_json={
            "zones_count": len(payload.zones),
            "service_rules_count": len(payload.service_rules),
            "currency": profile.currency,
        },
    )
    db.commit()
    db.refresh(profile)
    return _shipping_settings_out(db, profile=profile)


@router.get(
    "/settings",
    response_model=ShippingSettingsOut,
    summary="Get shipping settings",
    responses=error_responses(401, 403, 404, 500),
)
def get_shipping_settings(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    profile = _shipping_profile_for_business(db, business_id=access.business.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Shipping settings not configured")
    return _shipping_settings_out(db, profile=profile)


@router.post(
    "/checkout/{session_token}/quote",
    response_model=ShippingQuoteOut,
    summary="Quote shipping rates for checkout session",
    responses=error_responses(400, 404, 422, 500),
)
def quote_shipping_rates(
    session_token: str,
    payload: ShippingQuoteIn,
    db: Session = Depends(get_db),
):
    checkout = _checkout_by_token_or_404(db, session_token=session_token)
    profile = _shipping_profile_for_business(db, business_id=checkout.business_id)
    if not profile:
        raise HTTPException(status_code=400, detail="Shipping settings not configured")

    zones = db.execute(
        select(ShippingZone).where(ShippingZone.profile_id == profile.id)
    ).scalars().all()
    rules = db.execute(
        select(ShippingServiceRule).where(
            ShippingServiceRule.profile_id == profile.id,
            ShippingServiceRule.is_active.is_(True),
        )
    ).scalars().all()
    if not rules:
        raise HTTPException(status_code=400, detail="No active shipping service rules configured")

    zone = _resolve_zone_for_destination(
        zones=zones,
        destination_country=payload.destination_country,
        destination_state=payload.destination_state,
        destination_city=payload.destination_city,
        destination_postal_code=payload.destination_postal_code,
    )

    zone_rules = [rule for rule in rules if rule.zone_id == (zone.id if zone else None)]
    applicable_rules = zone_rules if zone_rules else [rule for rule in rules if rule.zone_id is None]
    if not applicable_rules:
        raise HTTPException(status_code=400, detail="No shipping rules for destination")

    option_rows: list[dict[str, object]] = []
    for rule in applicable_rules:
        amount = to_money(rule.base_rate) + (to_money(rule.per_kg_rate) * to_money(payload.total_weight_kg))
        amount += to_money(profile.handling_fee)
        option_rows.append(
            {
                "provider": rule.provider,
                "service_code": rule.service_code,
                "service_name": rule.service_name,
                "amount": float(to_money(amount)),
                "eta_min_days": rule.min_eta_days,
                "eta_max_days": rule.max_eta_days,
                "zone_name": zone.zone_name if zone else None,
            }
        )

    options: list[ShippingQuoteOptionOut] = []
    provider_rows: dict[str, list[dict[str, object]]] = {}
    for row in option_rows:
        provider_rows.setdefault(str(row["provider"]), []).append(row)

    for provider_name, provider_options in provider_rows.items():
        provider = get_carrier_provider(provider_name)
        quoted = provider.quote_rates(
            ShippingQuoteRequest(
                business_id=checkout.business_id,
                destination_country=payload.destination_country,
                destination_state=payload.destination_state,
                destination_city=payload.destination_city,
                destination_postal_code=payload.destination_postal_code,
                total_weight_kg=payload.total_weight_kg,
                currency=profile.currency,
                options=provider_options,
            )
        )
        options.extend(
            ShippingQuoteOptionOut(
                provider=item.provider,
                service_code=item.service_code,
                service_name=item.service_name,
                zone_name=item.zone_name,
                amount=item.amount,
                currency=item.currency,
                eta_min_days=item.eta_min_days,
                eta_max_days=item.eta_max_days,
            )
            for item in quoted
        )

    options.sort(key=lambda item: item.amount)
    return ShippingQuoteOut(
        checkout_session_token=checkout.session_token,
        currency=profile.currency,
        options=options,
    )


@router.post(
    "/checkout/{session_token}/select-rate",
    response_model=ShippingRateSelectionOut,
    summary="Select shipping rate for checkout session",
    responses=error_responses(400, 404, 422, 500),
)
def select_shipping_rate(
    session_token: str,
    payload: ShippingRateSelectIn,
    db: Session = Depends(get_db),
):
    checkout = _checkout_by_token_or_404(db, session_token=session_token)
    if checkout.status not in {"open", "pending_payment", "payment_failed"}:
        raise HTTPException(status_code=400, detail=f"Cannot select shipping rate when checkout status={checkout.status}")

    selection = db.execute(
        select(CheckoutShippingSelection).where(CheckoutShippingSelection.checkout_session_id == checkout.id)
    ).scalar_one_or_none()
    if not selection:
        selection = CheckoutShippingSelection(
            id=str(uuid.uuid4()),
            checkout_session_id=checkout.id,
            provider=payload.provider.lower(),
            service_code=payload.service_code,
            service_name=payload.service_name,
            zone_name=payload.zone_name,
            amount=to_money(payload.amount),
            currency=payload.currency.upper(),
            eta_min_days=payload.eta_min_days,
            eta_max_days=payload.eta_max_days,
        )
        db.add(selection)
    else:
        selection.provider = payload.provider.lower()
        selection.service_code = payload.service_code
        selection.service_name = payload.service_name
        selection.zone_name = payload.zone_name
        selection.amount = to_money(payload.amount)
        selection.currency = payload.currency.upper()
        selection.eta_min_days = payload.eta_min_days
        selection.eta_max_days = payload.eta_max_days

    db.commit()
    db.refresh(selection)
    return ShippingRateSelectionOut(
        checkout_session_id=checkout.id,
        provider=selection.provider,
        service_code=selection.service_code,
        service_name=selection.service_name,
        zone_name=selection.zone_name,
        amount=float(to_money(selection.amount)),
        currency=selection.currency,
        eta_min_days=selection.eta_min_days,
        eta_max_days=selection.eta_max_days,
        updated_at=selection.updated_at,
    )


@router.get(
    "/checkout/{session_token}/selected-rate",
    response_model=ShippingRateSelectionOut,
    summary="Get selected shipping rate for checkout session",
    responses=error_responses(404, 500),
)
def get_selected_shipping_rate(
    session_token: str,
    db: Session = Depends(get_db),
):
    checkout = _checkout_by_token_or_404(db, session_token=session_token)
    selection = db.execute(
        select(CheckoutShippingSelection).where(CheckoutShippingSelection.checkout_session_id == checkout.id)
    ).scalar_one_or_none()
    if not selection:
        raise HTTPException(status_code=404, detail="No shipping rate selected")
    return ShippingRateSelectionOut(
        checkout_session_id=checkout.id,
        provider=selection.provider,
        service_code=selection.service_code,
        service_name=selection.service_name,
        zone_name=selection.zone_name,
        amount=float(to_money(selection.amount)),
        currency=selection.currency,
        eta_min_days=selection.eta_min_days,
        eta_max_days=selection.eta_max_days,
        updated_at=selection.updated_at,
    )


@router.post(
    "/shipments",
    response_model=ShipmentOut,
    summary="Create shipment and purchase label",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_shipment(
    payload: ShipmentCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    order = db.execute(
        select(Order).where(Order.id == payload.order_id, Order.business_id == access.business.id)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_status = _normalize_order_status(order.status)
    if current_status not in {"paid", "processing"}:
        raise HTTPException(status_code=400, detail=f"Order status={order.status} is not ready for shipment")

    provider = get_carrier_provider(payload.provider)
    label_result = provider.buy_label(
        ShippingLabelRequest(
            business_id=access.business.id,
            order_id=order.id,
            provider=payload.provider,
            service_code=payload.service_code,
            service_name=payload.service_name,
            recipient_name=payload.recipient_name,
            address_line1=payload.address_line1,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            postal_code=payload.postal_code,
        )
    )

    shipment = Shipment(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        order_id=payload.order_id,
        checkout_session_id=payload.checkout_session_id,
        provider=label_result.provider,
        service_code=payload.service_code,
        service_name=payload.service_name,
        status="label_purchased",
        shipping_cost=to_money(payload.shipping_cost),
        currency=payload.currency.upper(),
        tracking_number=label_result.tracking_number,
        label_url=label_result.label_url,
        recipient_name=payload.recipient_name,
        recipient_phone=payload.recipient_phone,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        postal_code=payload.postal_code,
    )
    db.add(shipment)
    db.add(
        ShipmentTrackingEvent(
            id=str(uuid.uuid4()),
            shipment_id=shipment.id,
            status="label_purchased",
            description="Shipping label purchased",
            event_time=datetime.now(timezone.utc),
            raw_payload_json={"tracking_number": label_result.tracking_number},
        )
    )

    if current_status == "paid":
        _ensure_transition_allowed(current_status, "processing")
        order.status = "processing"

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="shipping.shipment.create",
        target_type="shipment",
        target_id=shipment.id,
        metadata_json={
            "order_id": shipment.order_id,
            "tracking_number": shipment.tracking_number,
            "provider": shipment.provider,
            "service_code": shipment.service_code,
        },
    )
    db.commit()
    db.refresh(shipment)
    return _shipment_out(db, shipment)


@router.get(
    "/shipments",
    response_model=ShipmentListOut,
    summary="List shipments",
    responses=error_responses(401, 403, 422, 500),
)
def list_shipments(
    order_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(Shipment.id)).where(Shipment.business_id == access.business.id)
    stmt = select(Shipment).where(Shipment.business_id == access.business.id)

    if order_id:
        count_stmt = count_stmt.where(Shipment.order_id == order_id)
        stmt = stmt.where(Shipment.order_id == order_id)
    if status:
        normalized = status.strip().lower()
        count_stmt = count_stmt.where(Shipment.status == normalized)
        stmt = stmt.where(Shipment.status == normalized)
        status = normalized

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(stmt.order_by(Shipment.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    items = [_shipment_out(db, row) for row in rows]
    count = len(items)
    return ShipmentListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        order_id=order_id,
        status=status,
    )


@router.post(
    "/shipments/{shipment_id}/sync-tracking",
    response_model=ShipmentTrackingSyncOut,
    summary="Sync shipment tracking and propagate order status",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def sync_shipment_tracking(
    shipment_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    shipment = _shipment_by_id_or_404(db, shipment_id=shipment_id, business_id=access.business.id)
    if not shipment.tracking_number:
        raise HTTPException(status_code=400, detail="Shipment has no tracking number")

    provider = get_carrier_provider(shipment.provider)
    provider_result = provider.track(tracking_number=shipment.tracking_number)

    if shipment.status in {"label_purchased", "created"}:
        next_status = "in_transit"
    elif shipment.status == "in_transit":
        next_status = "delivered"
    else:
        next_status = shipment.status

    event_time = datetime.now(timezone.utc)
    description = (
        "Shipment in transit" if next_status == "in_transit"
        else "Shipment delivered" if next_status == "delivered"
        else "Shipment status synced"
    )
    db.add(
        ShipmentTrackingEvent(
            id=str(uuid.uuid4()),
            shipment_id=shipment.id,
            status=next_status,
            description=description,
            event_time=event_time,
            raw_payload_json={
                "provider_events": [
                    {"status": event.status, "description": event.description}
                    for event in provider_result.events
                ]
            },
        )
    )

    shipment.status = next_status
    if next_status == "in_transit" and not shipment.shipped_at:
        shipment.shipped_at = event_time
    if next_status == "delivered":
        shipment.delivered_at = event_time

    order = db.execute(
        select(Order).where(Order.id == shipment.order_id, Order.business_id == shipment.business_id)
    ).scalar_one()
    current_order_status = _normalize_order_status(order.status)
    if next_status == "in_transit" and current_order_status == "paid":
        _ensure_transition_allowed(current_order_status, "processing")
        order.status = "processing"
        current_order_status = "processing"
    if next_status == "delivered" and current_order_status in {"paid", "processing"}:
        _ensure_transition_allowed(current_order_status, "fulfilled")
        order.status = "fulfilled"

    log_audit_event(
        db,
        business_id=shipment.business_id,
        actor_user_id=actor.id,
        action="shipping.shipment.sync_tracking",
        target_type="shipment",
        target_id=shipment.id,
        metadata_json={
            "shipment_status": shipment.status,
            "order_id": order.id,
            "order_status": order.status,
        },
    )
    db.commit()
    return ShipmentTrackingSyncOut(
        shipment_id=shipment.id,
        shipment_status=shipment.status,
        order_id=order.id,
        order_status=order.status,
        tracking_events_added=1,
    )
