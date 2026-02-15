import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.deps import get_db
from app.core.security_current import get_current_business
from app.schemas.sales import SaleCreate
from app.models.sales import Sale, SaleItem
from app.models.product import ProductVariant, Product
from app.services.inventory_service import add_ledger_entry, get_variant_stock

router = APIRouter(prefix="/sales", tags=["sales"])

@router.post("")
def create_sale(payload: SaleCreate, db: Session = Depends(get_db), biz=Depends(get_current_business)):
    if payload.payment_method not in {"cash", "transfer", "pos"}:
        raise HTTPException(status_code=400, detail="Invalid payment_method")
    if payload.channel not in {"whatsapp", "instagram", "walk-in"}:
        raise HTTPException(status_code=400, detail="Invalid channel")
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items")

    # validate and compute totals + check stock
    total = 0.0
    for item in payload.items:
        if item.qty <= 0 or item.unit_price <= 0:
            raise HTTPException(status_code=400, detail="qty and unit_price must be > 0")

        variant = db.execute(select(ProductVariant).where(ProductVariant.id == item.variant_id)).scalar_one()
        product = db.execute(select(Product).where(Product.id == variant.product_id)).scalar_one()
        if product.business_id != biz.id:
            raise HTTPException(status_code=403, detail="Contains item not in your business")

        stock = get_variant_stock(db, biz.id, item.variant_id)
        if stock < item.qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for variant {item.variant_id}")

        total += float(item.qty * item.unit_price)

    sale_id = str(uuid.uuid4())
    sale = Sale(
        id=sale_id,
        business_id=biz.id,
        payment_method=payload.payment_method,
        channel=payload.channel,
        total_amount=total,
    )
    db.add(sale)

    for item in payload.items:
        line_total = float(item.qty * item.unit_price)
        db.add(
            SaleItem(
                id=str(uuid.uuid4()),
                sale_id=sale_id,
                variant_id=item.variant_id,
                qty=item.qty,
                unit_price=item.unit_price,
                line_total=line_total,
            )
        )
        # stock out via ledger
        add_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=biz.id,
            variant_id=item.variant_id,
            qty_delta=-item.qty,
            reason="sale",
            reference_id=sale_id,
        )

    db.commit()
    return {"id": sale_id, "total": total}
