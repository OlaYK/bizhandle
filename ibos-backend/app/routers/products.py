import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, inspect as sa_inspect, or_, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_business, get_current_user
from app.models.inventory import InventoryLedger
from app.models.product import Product, ProductVariant
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.product import (
    ProductCreate,
    ProductCreateOut,
    ProductPublishIn,
    ProductPublishOut,
    ProductListOut,
    VariantCreate,
    VariantCreateOut,
    VariantPublishIn,
    VariantPublishOut,
    VariantListOut,
    VariantOut,
)
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/products", tags=["products"])
MAX_PRODUCT_PAGE_SIZE = 500


def _table_has_column(db: Session, *, table_name: str, column_name: str) -> bool:
    bind = db.get_bind()
    if bind is None:
        return False
    inspector = sa_inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


@router.post(
    "",
    response_model=ProductCreateOut,
    summary="Create product",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    biz = access.business
    p = Product(
        id=str(uuid.uuid4()),
        business_id=biz.id,
        name=payload.name,
        category=payload.category,
    )
    db.add(p)
    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="product.create",
        target_type="product",
        target_id=p.id,
        metadata_json={"name": p.name, "category": p.category},
    )
    db.commit()
    return ProductCreateOut(id=p.id)


@router.post(
    "/{product_id}/variants",
    response_model=VariantCreateOut,
    summary="Create product variant",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def create_variant(
    product_id: str,
    payload: VariantCreate,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    biz = access.business
    resolved_product_id = db.execute(
        select(Product.id).where(Product.id == product_id, Product.business_id == biz.id)
    ).scalar_one_or_none()
    if not resolved_product_id:
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
        product_id=resolved_product_id,
        size=payload.size,
        label=payload.label,
        sku=payload.sku,
        reorder_level=payload.reorder_level,
        cost_price=payload.cost_price,
        selling_price=payload.selling_price,
    )
    db.add(v)
    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="product.variant.create",
        target_type="product_variant",
        target_id=v.id,
        metadata_json={
            "product_id": v.product_id,
            "size": v.size,
            "label": v.label,
            "sku": v.sku,
            "reorder_level": v.reorder_level,
        },
    )
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
    limit: int = Query(default=50, ge=1, le=MAX_PRODUCT_PAGE_SIZE, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    has_products_is_published = _table_has_column(
        db, table_name="products", column_name="is_published"
    )
    total = int(
        db.execute(select(func.count(Product.id)).where(Product.business_id == biz.id)).scalar_one()
    )
    product_columns = [
        Product.id.label("id"),
        Product.name.label("name"),
        Product.category.label("category"),
        Product.active.label("active"),
    ]
    if has_products_is_published:
        product_columns.append(Product.is_published.label("is_published"))
    rows = db.execute(
        select(*product_columns)
        .where(Product.business_id == biz.id)
        .order_by(Product.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).mappings().all()
    items = [
        {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "active": bool(row["active"]) if row["active"] is not None else True,
            "is_published": bool(row["is_published"]) if has_products_is_published else False,
        }
        for row in rows
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
    limit: int = Query(default=50, ge=1, le=MAX_PRODUCT_PAGE_SIZE, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    resolved_product_id = db.execute(
        select(Product.id).where(Product.id == product_id, Product.business_id == biz.id)
    ).scalar_one_or_none()
    if not resolved_product_id:
        raise HTTPException(status_code=404, detail="Product not found")

    has_variant_business_id = _table_has_column(
        db, table_name="product_variants", column_name="business_id"
    )
    has_variant_reorder_level = _table_has_column(
        db, table_name="product_variants", column_name="reorder_level"
    )
    has_variant_is_published = _table_has_column(
        db, table_name="product_variants", column_name="is_published"
    )

    count_stmt = select(func.count(ProductVariant.id)).where(
        ProductVariant.product_id == resolved_product_id,
    )
    if has_variant_business_id:
        count_stmt = count_stmt.where(
            or_(
                ProductVariant.business_id == biz.id,
                ProductVariant.business_id.is_(None),
            )
        )
    total = int(db.execute(count_stmt).scalar_one())

    variant_columns = [
        ProductVariant.id.label("id"),
        ProductVariant.product_id.label("product_id"),
        ProductVariant.size.label("size"),
        ProductVariant.label.label("label"),
        ProductVariant.sku.label("sku"),
        ProductVariant.cost_price.label("cost_price"),
        ProductVariant.selling_price.label("selling_price"),
        ProductVariant.created_at.label("created_at"),
    ]
    if has_variant_business_id:
        variant_columns.append(ProductVariant.business_id.label("business_id"))
    if has_variant_reorder_level:
        variant_columns.append(ProductVariant.reorder_level.label("reorder_level"))
    if has_variant_is_published:
        variant_columns.append(ProductVariant.is_published.label("is_published"))

    variant_stmt = select(*variant_columns).where(
        ProductVariant.product_id == resolved_product_id,
    )
    if has_variant_business_id:
        variant_stmt = variant_stmt.where(
            or_(
                ProductVariant.business_id == biz.id,
                ProductVariant.business_id.is_(None),
            )
        )
    variants = db.execute(
        variant_stmt
        .order_by(ProductVariant.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).mappings().all()
    variant_ids = [row["id"] for row in variants]

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
            id=row["id"],
            product_id=row["product_id"],
            business_id=row.get("business_id") or biz.id,
            size=row["size"],
            label=row["label"],
            sku=row["sku"],
            reorder_level=int(row.get("reorder_level") or 0),
            cost_price=float(row["cost_price"]) if row["cost_price"] is not None else None,
            selling_price=float(row["selling_price"]) if row["selling_price"] is not None else None,
            is_published=bool(row["is_published"]) if has_variant_is_published else False,
            stock=stock_by_variant.get(row["id"], 0),
            created_at=row["created_at"],
        )
        for row in variants
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


@router.patch(
    "/{product_id}/publish",
    response_model=ProductPublishOut,
    summary="Set product publish status",
    responses=error_responses(401, 403, 404, 422, 500),
)
def set_product_publish_status(
    product_id: str,
    payload: ProductPublishIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    biz = access.business
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.business_id == biz.id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_published = payload.is_published
    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="product.publish.update",
        target_type="product",
        target_id=product.id,
        metadata_json={"is_published": product.is_published},
    )
    db.commit()
    return ProductPublishOut(id=product.id, is_published=product.is_published)


@router.patch(
    "/{product_id}/variants/{variant_id}/publish",
    response_model=VariantPublishOut,
    summary="Set variant publish status",
    responses=error_responses(401, 403, 404, 422, 500),
)
def set_variant_publish_status(
    product_id: str,
    variant_id: str,
    payload: VariantPublishIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    biz = access.business
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.business_id == biz.id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant = db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product.id,
            ProductVariant.business_id == biz.id,
        )
    ).scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    variant.is_published = payload.is_published
    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="product.variant.publish.update",
        target_type="product_variant",
        target_id=variant.id,
        metadata_json={"product_id": product.id, "is_published": variant.is_published},
    )
    db.commit()
    return VariantPublishOut(
        id=variant.id,
        product_id=product.id,
        is_published=variant.is_published,
    )
