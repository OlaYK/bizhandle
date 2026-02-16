import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.config import settings
from app.core.deps import get_db
from app.core.money import to_money
from app.core.security_current import get_current_business
from app.models.inventory import InventoryLedger
from app.models.product import Product, ProductVariant
from app.schemas.common import PaginationMeta
from app.schemas.inventory import (
    InventoryLedgerEntryOut,
    InventoryLedgerListOut,
    LowStockListOut,
    LowStockVariantOut,
    StockAdjustIn,
    StockIn,
    StockLevelOut,
    StockOut,
)
from app.services.inventory_service import add_ledger_entry, get_variant_stock

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _get_variant_in_business(db: Session, *, business_id: str, variant_id: str) -> ProductVariant:
    variant = db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


@router.post(
    "/stock-in",
    response_model=StockOut,
    summary="Add stock to a variant",
    responses=error_responses(400, 401, 404, 422, 500),
)
def stock_in(
    payload: StockIn,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    _get_variant_in_business(db, business_id=biz.id, variant_id=payload.variant_id)

    add_ledger_entry(
        db,
        ledger_id=str(uuid.uuid4()),
        business_id=biz.id,
        variant_id=payload.variant_id,
        qty_delta=payload.qty,
        reason="stock_in",
        unit_cost=to_money(payload.unit_cost) if payload.unit_cost is not None else None,
    )
    db.commit()
    return StockOut()


@router.post(
    "/adjust",
    response_model=StockOut,
    summary="Manual stock adjustment",
    responses=error_responses(400, 401, 404, 422, 500),
)
def adjust_stock(
    payload: StockAdjustIn,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    _get_variant_in_business(db, business_id=biz.id, variant_id=payload.variant_id)

    if payload.qty_delta < 0:
        current_stock = get_variant_stock(db, biz.id, payload.variant_id)
        if current_stock < abs(payload.qty_delta):
            raise HTTPException(status_code=400, detail="Insufficient stock for adjustment")

    add_ledger_entry(
        db,
        ledger_id=str(uuid.uuid4()),
        business_id=biz.id,
        variant_id=payload.variant_id,
        qty_delta=payload.qty_delta,
        reason="adjustment",
        note=f"{payload.reason}: {payload.note}" if payload.note else payload.reason,
        unit_cost=to_money(payload.unit_cost) if payload.unit_cost is not None else None,
    )
    db.commit()
    return StockOut()


@router.get(
    "/stock/{variant_id}",
    response_model=StockLevelOut,
    summary="Get stock level for a variant",
    responses=error_responses(401, 404, 422, 500),
)
def get_stock(
    variant_id: str,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    _get_variant_in_business(db, business_id=biz.id, variant_id=variant_id)
    stock = get_variant_stock(db, biz.id, variant_id)
    return StockLevelOut(variant_id=variant_id, stock=stock)


@router.get(
    "/ledger",
    response_model=InventoryLedgerListOut,
    summary="List inventory ledger entries",
    responses={
        200: {
            "description": "Paginated inventory ledger",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "ledger-id",
                                "variant_id": "variant-id",
                                "qty_delta": -2,
                                "reason": "sale",
                                "reference_id": "sale-id",
                                "note": "Walk-in purchase",
                                "unit_cost": 45.0,
                                "created_at": "2026-02-16T10:00:00Z",
                            }
                        ],
                        "pagination": {
                            "total": 12,
                            "limit": 50,
                            "offset": 0,
                            "count": 1,
                            "has_next": True,
                        },
                    }
                }
            },
        },
        **error_responses(401, 404, 422, 500),
    },
)
def list_inventory_ledger(
    variant_id: str | None = Query(default=None, description="Optional variant filter"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if variant_id:
        _get_variant_in_business(db, business_id=biz.id, variant_id=variant_id)

    count_stmt = select(func.count(InventoryLedger.id)).where(InventoryLedger.business_id == biz.id)
    stmt = select(InventoryLedger).where(InventoryLedger.business_id == biz.id)
    if variant_id:
        count_stmt = count_stmt.where(InventoryLedger.variant_id == variant_id)
        stmt = stmt.where(InventoryLedger.variant_id == variant_id)

    total = int(db.execute(count_stmt).scalar_one())
    stmt = stmt.order_by(InventoryLedger.created_at.desc()).offset(offset).limit(limit)
    rows = db.execute(stmt).scalars().all()
    items = [
        InventoryLedgerEntryOut(
            id=row.id,
            variant_id=row.variant_id,
            qty_delta=row.qty_delta,
            reason=row.reason,
            reference_id=row.reference_id,
            note=row.note,
            unit_cost=float(row.unit_cost) if row.unit_cost is not None else None,
            created_at=row.created_at,
        )
        for row in rows
    ]
    count = len(items)
    return InventoryLedgerListOut(
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
    response_model=LowStockListOut,
    summary="List low-stock variants",
    responses={
        200: {
            "description": "Paginated low-stock variants",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "variant_id": "variant-id",
                                "product_id": "product-id",
                                "product_name": "Ankara Fabric",
                                "size": "6x6",
                                "label": "Plain",
                                "sku": "ANK-6X6-PLN",
                                "reorder_level": 5,
                                "stock": 3,
                            }
                        ],
                        "pagination": {
                            "total": 1,
                            "limit": 100,
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
def list_low_stock_variants(
    threshold: int | None = Query(
        default=None,
        ge=0,
        description="Optional global threshold override. Defaults to variant reorder level or configured default.",
    ),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    variants = db.execute(
        select(ProductVariant, Product.name)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.business_id == biz.id)
        .order_by(ProductVariant.created_at.desc())
    ).all()

    if not variants:
        return LowStockListOut(
            items=[],
            pagination=PaginationMeta(total=0, limit=limit, offset=offset, count=0, has_next=False),
        )

    variant_ids = [row[0].id for row in variants]
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

    result: list[LowStockVariantOut] = []
    default_threshold = settings.low_stock_default_threshold
    for variant, product_name in variants:
        current_stock = stock_by_variant.get(variant.id, 0)
        limit_threshold = threshold
        if limit_threshold is None:
            limit_threshold = variant.reorder_level if variant.reorder_level > 0 else default_threshold

        if current_stock <= limit_threshold:
            result.append(
                LowStockVariantOut(
                    variant_id=variant.id,
                    product_id=variant.product_id,
                    product_name=product_name,
                    size=variant.size,
                    label=variant.label,
                    sku=variant.sku,
                    reorder_level=variant.reorder_level,
                    stock=current_stock,
                )
            )
    total = len(result)
    page_items = result[offset : offset + limit]
    count = len(page_items)
    return LowStockListOut(
        items=page_items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )
