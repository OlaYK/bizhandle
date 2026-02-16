from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.inventory import InventoryLedger

def get_variant_stock(db: Session, business_id: str, variant_id: str) -> int:
    q = select(func.coalesce(func.sum(InventoryLedger.qty_delta), 0)).where(
        InventoryLedger.business_id == business_id,
        InventoryLedger.variant_id == variant_id,
    )
    return int(db.execute(q).scalar_one())

def add_ledger_entry(
    db: Session,
    *,
    ledger_id: str,
    business_id: str,
    variant_id: str,
    qty_delta: int,
    reason: str,
    reference_id: str | None = None,
    note: str | None = None,
    unit_cost: Decimal | None = None,
) -> InventoryLedger:
    entry = InventoryLedger(
        id=ledger_id,
        business_id=business_id,
        variant_id=variant_id,
        qty_delta=qty_delta,
        reason=reason,
        reference_id=reference_id,
        note=note,
        unit_cost=unit_cost,
    )
    db.add(entry)
    return entry
