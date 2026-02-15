import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.deps import get_db
from app.core.security_current import get_current_business
from app.models.product import Product, ProductVariant
from app.schemas.product import ProductCreate, VariantCreate

router = APIRouter(prefix="/products", tags=["products"])

@router.post("")
def create_product(payload: ProductCreate, db: Session = Depends(get_db), biz=Depends(get_current_business)):
    p = Product(id=str(uuid.uuid4()), business_id=biz.id, name=payload.name, category=payload.category)
    db.add(p)
    db.commit()
    return {"id": p.id}

@router.post("/{product_id}/variants")
def create_variant(product_id: str, payload: VariantCreate, db: Session = Depends(get_db), biz=Depends(get_current_business)):
    # ensure product belongs to business
    prod = db.execute(select(Product).where(Product.id == product_id, Product.business_id == biz.id)).scalar_one()
    v = ProductVariant(
        id=str(uuid.uuid4()),
        product_id=prod.id,
        size=payload.size,
        label=payload.label,
        sku=payload.sku,
        cost_price=payload.cost_price,
        selling_price=payload.selling_price,
    )
    db.add(v)
    db.commit()
    return {"id": v.id}

@router.get("")
def list_products(db: Session = Depends(get_db), biz=Depends(get_current_business)):
    rows = db.execute(select(Product).where(Product.business_id == biz.id)).scalars().all()
    return [{"id": r.id, "name": r.name, "category": r.category, "active": r.active} for r in rows]
