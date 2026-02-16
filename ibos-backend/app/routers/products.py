import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.schemas.common import PaginationMeta
from app.core.security_current import get_current_business
from app.models.inventory import InventoryLedger
from app.models.product import Product, ProductVariant
from app.schemas.product import (
    ProductCreate,
    ProductCreateOut,
    ProductListOut,
    VariantCreate,
    VariantCreateOut,
    VariantListOut,
    VariantOut,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post(
    "",
    response_model=ProductCreateOut,
    summary="Create product",
    responses=error_responses(400, 401, 404, 422, 500),
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    p = Product(
        id=str(uuid.uuid4()),
        business_id=biz.id,
        name=payload.name,
        category=payload.category,
    )
    db.add(p)
    db.commit()
    return ProductCreateOut(id=p.id)


@router.post(
    "/{product_id}/variants",
    response_model=VariantCreateOut,
    summary="Create product variant",
    responses=error_responses(400, 401, 404, 422, 500),
)
def create_variant(
    product_id: str,
    payload: VariantCreate,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    prod = db.execute(
        select(Product).where(Product.id == product_id, Product.business_id == biz.id)
    ).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.sku:
        sku_exists = db.execute(
            select(ProductVariant.id).where(
                ProductVariant.business_id == biz.id,
                func.lower(ProductVariant.sku) == payload.sku.lower(),
            )
        ).scalar_one_or_none()
        if sku_exists:
            raise HTTPException(status_code=400, detail="SKU already exists")

    v = ProductVariant(
        id=str(uuid.uuid4()),
        business_id=biz.id,
        product_id=prod.id,
        size=payload.size,
        label=payload.label,
        sku=payload.sku,
        reorder_level=payload.reorder_level,
        cost_price=payload.cost_price,
        selling_price=payload.selling_price,
    )
    db.add(v)
    db.commit()
    return VariantCreateOut(id=v.id)


@router.get(
    "",
    response_model=ProductListOut,
    summary="List products",
    responses={
        200: {
            "description": "Paginated products",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "product-id",
                                "name": "Ankara Fabric",
                                "category": "fabrics",
                                "active": True,
                            }
                        ],
                        "pagination": {
                            "total": 1,
                            "limit": 50,
                            "offset": 0,
                            "count": 1,
                            "has_next": False,
                        },
                    }
                }
            },
        },
        **error_responses(401, 422, 500),
    },
)
def list_products(
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    total = int(
        db.execute(select(func.count(Product.id)).where(Product.business_id == biz.id)).scalar_one()
    )
    rows = db.execute(
        select(Product)
        .where(Product.business_id == biz.id)
        .order_by(Product.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    items = [
        {"id": r.id, "name": r.name, "category": r.category, "active": r.active}
        for r in rows
    ]
    count = len(items)
    return ProductListOut(
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
    "/{product_id}/variants",
    response_model=VariantListOut,
    summary="List product variants with current stock",
    responses={
        200: {
            "description": "Paginated product variants",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "variant-id",
                                "product_id": "product-id",
                                "business_id": "business-id",
                                "size": "6x6",
                                "label": "Plain",
                                "sku": "ANK-6X6-PLN",
                                "reorder_level": 5,
                                "cost_price": 50.0,
                                "selling_price": 100.0,
                                "stock": 12,
                                "created_at": "2026-02-16T10:00:00Z",
                            }
                        ],
                        "pagination": {
                            "total": 1,
                            "limit": 50,
                            "offset": 0,
                            "count": 1,
                            "has_next": False,
                        },
                    }
                }
            },
        },
        **error_responses(401, 404, 422, 500),
    },
)
def list_product_variants(
    product_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.business_id == biz.id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    total = int(
        db.execute(
            select(func.count(ProductVariant.id)).where(
                ProductVariant.product_id == product_id,
                ProductVariant.business_id == biz.id,
            )
        ).scalar_one()
    )

    variants = db.execute(
        select(ProductVariant)
        .where(
            ProductVariant.product_id == product_id,
            ProductVariant.business_id == biz.id,
        )
        .order_by(ProductVariant.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    variant_ids = [v.id for v in variants]

    stock_by_variant: dict[str, int] = {}
    if variant_ids:
        stock_rows = db.execute(
            select(
                InventoryLedger.variant_id,
                func.coalesce(func.sum(InventoryLedger.qty_delta), 0),
            )
            .where(
                InventoryLedger.business_id == biz.id,
                InventoryLedger.variant_id.in_(variant_ids),
            )
            .group_by(InventoryLedger.variant_id)
        ).all()
        stock_by_variant = {variant_id: int(stock) for variant_id, stock in stock_rows}

    items = [
        VariantOut(
            id=v.id,
            product_id=v.product_id,
            business_id=v.business_id,
            size=v.size,
            label=v.label,
            sku=v.sku,
            reorder_level=v.reorder_level,
            cost_price=float(v.cost_price) if v.cost_price is not None else None,
            selling_price=float(v.selling_price) if v.selling_price is not None else None,
            stock=stock_by_variant.get(v.id, 0),
            created_at=v.created_at,
        )
        for v in variants
    ]
    count = len(items)
    return VariantListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )
