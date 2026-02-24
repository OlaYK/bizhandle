from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.location import LocationInventoryLedger


def add_location_ledger_entry(
    db: Session,
    *,
    ledger_id: str,
    business_id: str,
    location_id: str,
    variant_id: str,
    qty_delta: int,
    reason: str,
    reference_id: str | None = None,
    note: str | None = None,
) -> LocationInventoryLedger:
    entry = LocationInventoryLedger(
        id=ledger_id,
        business_id=business_id,
        location_id=location_id,
        variant_id=variant_id,
        qty_delta=qty_delta,
        reason=reason,
        reference_id=reference_id,
        note=note,
    )
    db.add(entry)
    return entry


def get_location_variant_stock(
    db: Session,
    *,
    business_id: str,
    location_id: str,
    variant_id: str,
) -> int:
    q = select(func.coalesce(func.sum(LocationInventoryLedger.qty_delta), 0)).where(
        LocationInventoryLedger.business_id == business_id,
        LocationInventoryLedger.location_id == location_id,
        LocationInventoryLedger.variant_id == variant_id,
    )
    return int(db.execute(q).scalar_one())
