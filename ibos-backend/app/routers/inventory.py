import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from app.core.deps import get_db
from app.core.security_current import get_current_business
from app.models.product import ProductVariant, Product
from app.services.inventory_service import add_ledger_entry, get_variant_stock

router = APIRouter(prefix="/inventory", tags=["inventory"])

class StockIn(BaseModel):
    variant_id: str
    qty: int
    unit_cost: float | None = None

@router.post("/stock-in")
def stock_in(payload: StockIn, db: Session = Depends(get_db), biz=Depends(get_current_business)):
    if payload.qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be > 0")

    # validate variant belongs to business via product
    variant = db.execute(select(ProductVariant).where(ProductVariant.id == payload.variant_id)).scalar_one()
    product = db.execute(select(Product).where(Product.id == variant.product_id)).scalar_one()
    if product.business_id != biz.id:
        raise HTTPException(status_code=403, detail="Not your variant")

    add_ledger_entry(
        db,
        ledger_id=str(uuid.uuid4()),
        business_id=biz.id,
        variant_id=payload.variant_id,
        qty_delta=payload.qty,
        reason="stock_in",
        unit_cost=payload.unit_cost,
    )
    db.commit()
    return {"ok": True}

@router.get("/stock/{variant_id}")
def get_stock(variant_id: str, db: Session = Depends(get_db), biz=Depends(get_current_business)):
    stock = get_variant_stock(db, biz.id, variant_id)
    return {"variant_id": variant_id, "stock": stock}
