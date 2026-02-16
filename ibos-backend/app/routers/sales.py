import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import ZERO_MONEY, to_money
from app.core.security_current import get_current_business
from app.models.product import ProductVariant
from app.models.sales import Sale, SaleItem
from app.schemas.common import PaginationMeta
from app.schemas.sales import RefundCreate, SaleCreate, SaleCreateOut, SaleListOut, SaleOut
from app.services.inventory_service import add_ledger_entry, get_variant_stock

router = APIRouter(prefix="/sales", tags=["sales"])


def _variant_business_map(db: Session, variant_ids: list[str]) -> dict[str, str]:
    rows = db.execute(
        select(ProductVariant.id, ProductVariant.business_id).where(
            ProductVariant.id.in_(variant_ids)
        )
    ).all()
    return {variant_id: business_id for variant_id, business_id in rows}


@router.post(
    "",
    response_model=SaleCreateOut,
    summary="Create sale",
    description="Creates a sale, sale items, and matching stock-out ledger entries.",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_sale(
    payload: SaleCreate,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items")

    quantity_by_variant: dict[str, int] = {}
    total = ZERO_MONEY
    for item in payload.items:
        quantity_by_variant[item.variant_id] = quantity_by_variant.get(item.variant_id, 0) + item.qty
        total += to_money(item.unit_price) * item.qty

    variant_ids = list(quantity_by_variant.keys())
    business_by_variant = _variant_business_map(db, variant_ids)

    for variant_id in variant_ids:
        variant_business = business_by_variant.get(variant_id)
        if not variant_business:
            raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")
        if variant_business != biz.id:
            raise HTTPException(status_code=403, detail="Contains item not in your business")

        stock = get_variant_stock(db, biz.id, variant_id)
        if stock < quantity_by_variant[variant_id]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for variant {variant_id}",
            )

    sale_id = str(uuid.uuid4())
    sale = Sale(
        id=sale_id,
        business_id=biz.id,
        payment_method=payload.payment_method,
        channel=payload.channel,
        note=payload.note,
        total_amount=to_money(total),
        kind="sale",
    )
    db.add(sale)

    for item in payload.items:
        unit_price = to_money(item.unit_price)
        line_total = to_money(unit_price * item.qty)
        db.add(
            SaleItem(
                id=str(uuid.uuid4()),
                sale_id=sale_id,
                variant_id=item.variant_id,
                qty=item.qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
        add_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=biz.id,
            variant_id=item.variant_id,
            qty_delta=-item.qty,
            reason="sale",
            reference_id=sale_id,
            note=payload.note,
        )

    db.commit()
    return SaleCreateOut(id=sale_id, total=float(to_money(total)))


def _resolve_refund_unit_prices(
    db: Session, *, sale_id: str, variant_ids: list[str]
) -> dict[str, Decimal]:
    rows = db.execute(
        select(
            SaleItem.variant_id,
            func.coalesce(func.sum(SaleItem.line_total), 0),
            func.coalesce(func.sum(SaleItem.qty), 0),
        )
        .where(SaleItem.sale_id == sale_id, SaleItem.variant_id.in_(variant_ids))
        .group_by(SaleItem.variant_id)
    ).all()

    unit_prices: dict[str, Decimal] = {}
    for variant_id, line_total, qty in rows:
        qty_int = int(qty)
        if qty_int <= 0:
            continue
        unit_prices[variant_id] = to_money(Decimal(line_total) / qty_int)
    return unit_prices


@router.post(
    "/{sale_id}/refund",
    response_model=SaleCreateOut,
    summary="Create refund",
    description="Records a refund as a negative sale and re-stocks inventory.",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_refund(
    sale_id: str,
    payload: RefundCreate,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items")

    original_sale = db.execute(
        select(Sale).where(
            Sale.id == sale_id,
            Sale.business_id == biz.id,
        )
    ).scalar_one_or_none()
    if not original_sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if original_sale.kind != "sale":
        raise HTTPException(status_code=400, detail="Only normal sales can be refunded")

    variant_ids = [item.variant_id for item in payload.items]
    business_by_variant = _variant_business_map(db, variant_ids)
    for variant_id in variant_ids:
        variant_business = business_by_variant.get(variant_id)
        if not variant_business:
            raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")
        if variant_business != biz.id:
            raise HTTPException(status_code=403, detail="Variant is not in your business")

    sold_rows = db.execute(
        select(SaleItem.variant_id, func.coalesce(func.sum(SaleItem.qty), 0))
        .where(SaleItem.sale_id == sale_id)
        .group_by(SaleItem.variant_id)
    ).all()
    sold_by_variant = {variant_id: int(qty) for variant_id, qty in sold_rows}

    refunded_rows = db.execute(
        select(SaleItem.variant_id, func.coalesce(func.sum(SaleItem.qty), 0))
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(
            Sale.parent_sale_id == sale_id,
            Sale.kind == "refund",
        )
        .group_by(SaleItem.variant_id)
    ).all()
    refunded_by_variant = {variant_id: abs(int(qty)) for variant_id, qty in refunded_rows}

    source_unit_prices = _resolve_refund_unit_prices(db, sale_id=sale_id, variant_ids=variant_ids)
    refund_total = ZERO_MONEY
    normalized_items: list[tuple[str, int, Decimal]] = []

    requested_qty_by_variant: dict[str, int] = {}
    for item in payload.items:
        requested_qty_by_variant[item.variant_id] = requested_qty_by_variant.get(item.variant_id, 0) + item.qty

    for variant_id, requested_qty in requested_qty_by_variant.items():
        sold_qty = sold_by_variant.get(variant_id, 0)
        already_refunded = refunded_by_variant.get(variant_id, 0)
        available_for_refund = sold_qty - already_refunded
        if sold_qty <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Variant {variant_id} was not part of this sale",
            )
        if requested_qty > available_for_refund:
            raise HTTPException(
                status_code=400,
                detail=f"Refund quantity exceeds remaining sold quantity for variant {variant_id}",
            )

    for item in payload.items:
        unit_price = (
            to_money(item.unit_price)
            if item.unit_price is not None
            else source_unit_prices.get(item.variant_id)
        )
        if unit_price is None:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot infer unit price for variant {item.variant_id}; provide unit_price.",
            )
        refund_total += unit_price * item.qty
        normalized_items.append((item.variant_id, item.qty, unit_price))

    refund_sale_id = str(uuid.uuid4())
    refund_sale = Sale(
        id=refund_sale_id,
        business_id=biz.id,
        payment_method=payload.payment_method or original_sale.payment_method,
        channel=payload.channel or original_sale.channel,
        note=payload.note,
        kind="refund",
        parent_sale_id=sale_id,
        total_amount=to_money(-refund_total),
    )
    db.add(refund_sale)

    for variant_id, qty, unit_price in normalized_items:
        line_total = to_money(unit_price * qty)
        db.add(
            SaleItem(
                id=str(uuid.uuid4()),
                sale_id=refund_sale_id,
                variant_id=variant_id,
                qty=-qty,
                unit_price=unit_price,
                line_total=to_money(-line_total),
            )
        )
        add_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=biz.id,
            variant_id=variant_id,
            qty_delta=qty,
            reason="refund",
            reference_id=refund_sale_id,
            note=payload.note,
        )

    db.commit()
    return SaleCreateOut(id=refund_sale_id, total=float(to_money(-refund_total)))


@router.get(
    "",
    response_model=SaleListOut,
    summary="List sales",
    responses={
        200: {
            "description": "Paginated sales",
            "content": {
                "application/json": {
                    "example": {
                        "pagination": {
                            "total": 2,
                            "limit": 50,
                            "offset": 0,
                            "count": 2,
                            "has_next": False,
                        },
                        "start_date": None,
                        "end_date": None,
                        "items": [
                            {
                                "id": "sale-id",
                                "kind": "sale",
                                "parent_sale_id": None,
                                "payment_method": "cash",
                                "channel": "walk-in",
                                "note": "Customer bought 2 units",
                                "total_amount": 240.0,
                                "created_at": "2026-02-16T10:00:00Z",
                            }
                        ],
                    }
                }
            },
        },
        **error_responses(400, 401, 422, 500),
    },
)
def list_sales(
    start_date: date | None = Query(default=None, description="Filter from date (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="Filter to date (YYYY-MM-DD)"),
    include_refunds: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    count_stmt = select(func.count(Sale.id)).where(Sale.business_id == biz.id)
    data_stmt = select(Sale).where(Sale.business_id == biz.id)

    if not include_refunds:
        count_stmt = count_stmt.where(Sale.kind == "sale")
        data_stmt = data_stmt.where(Sale.kind == "sale")

    if start_date:
        count_stmt = count_stmt.where(func.date(Sale.created_at) >= start_date)
        data_stmt = data_stmt.where(func.date(Sale.created_at) >= start_date)
    if end_date:
        count_stmt = count_stmt.where(func.date(Sale.created_at) <= end_date)
        data_stmt = data_stmt.where(func.date(Sale.created_at) <= end_date)

    total_count = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        data_stmt.order_by(Sale.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    items = [
        SaleOut(
            id=row.id,
            kind=row.kind,
            parent_sale_id=row.parent_sale_id,
            payment_method=row.payment_method,
            channel=row.channel,
            note=row.note,
            total_amount=float(to_money(row.total_amount)),
            created_at=row.created_at,
        )
        for row in rows
    ]
    count = len(items)

    return SaleListOut(
        pagination=PaginationMeta(
            total=total_count,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total_count,
        ),
        start_date=start_date,
        end_date=end_date,
        items=items,
    )
