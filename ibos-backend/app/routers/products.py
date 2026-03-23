import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, inspect as sa_inspect, or_, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_business, get_current_user
from app.models.inventory import InventoryLedger
from app.models.location import Location, LocationInventoryLedger
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
    VariantUpdateIn,
    VariantUpdateOut,
    VariantPublishIn,
    VariantPublishOut,
    VariantListOut,
    VariantOut,
)
from app.services.audit_service import log_audit_event
from app.services.display_service import get_product_default_variant_map
from app.services.inventory_service import add_ledger_entry

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
        image_url=payload.image_url,
        reorder_level=payload.reorder_level,
        cost_price=payload.cost_price,
        selling_price=payload.selling_price,
    )
    db.add(v)
    if payload.qty > 0:
        add_ledger_entry(
            db,
            ledger_id=str(uuid.uuid4()),
            business_id=biz.id,
            variant_id=v.id,
            qty_delta=payload.qty,
            reason="stock_in",
            note="Initial stock added during variant creation",
            unit_cost=payload.cost_price,
        )
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
            "image_url": v.image_url,
            "reorder_level": v.reorder_level,
            "qty": payload.qty,
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
    has_variant_business_id = _table_has_column(
        db, table_name="product_variants", column_name="business_id"
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
    product_ids = [row["id"] for row in rows]
    variant_count_stmt = (
        select(ProductVariant.product_id, func.count(ProductVariant.id))
        .where(ProductVariant.product_id.in_(product_ids))
        .group_by(ProductVariant.product_id)
    )
    if has_variant_business_id:
        variant_count_stmt = variant_count_stmt.where(
            or_(
                ProductVariant.business_id == biz.id,
                ProductVariant.business_id.is_(None),
            )
        )
    variant_count_map = {
        product_id: int(count)
        for product_id, count in db.execute(variant_count_stmt).all()
    } if product_ids else {}
    default_variant_map = get_product_default_variant_map(
        db,
        business_id=biz.id,
        product_ids=product_ids,
    )
    items = [
        {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "active": bool(row["active"]) if row["active"] is not None else True,
            "is_published": bool(row["is_published"]) if has_products_is_published else False,
            "variant_count": variant_count_map.get(row["id"], 0),
            "default_variant_id": default_variant_map.get(row["id"]).variant_id if row["id"] in default_variant_map else None,
            "default_sku": default_variant_map.get(row["id"]).sku if row["id"] in default_variant_map else None,
            "default_selling_price": (
                float(default_variant_map.get(row["id"]).selling_price)
                if row["id"] in default_variant_map and default_variant_map.get(row["id"]).selling_price is not None
                else None
            ),
            "default_stock": default_variant_map.get(row["id"]).stock if row["id"] in default_variant_map else None,
            "default_image_url": default_variant_map.get(row["id"]).image_url if row["id"] in default_variant_map else None,
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
    location_id: str | None = Query(default=None, description="Optional location context for stock lookup"),
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
    if location_id:
        resolved_location_id = db.execute(
            select(Location.id).where(Location.id == location_id, Location.business_id == biz.id)
        ).scalar_one_or_none()
        if not resolved_location_id:
            raise HTTPException(status_code=404, detail="Location not found")

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
        ProductVariant.image_url.label("image_url"),
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
    variant_stmt = variant_stmt.join(Product, Product.id == ProductVariant.product_id)
    variant_stmt = variant_stmt.add_columns(Product.name.label("product_name"))
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

    location_stock_by_variant: dict[str, int] = {}
    if variant_ids and location_id:
        location_rows = db.execute(
            select(
                LocationInventoryLedger.variant_id,
                func.coalesce(func.sum(LocationInventoryLedger.qty_delta), 0),
            )
            .where(
                LocationInventoryLedger.business_id == biz.id,
                LocationInventoryLedger.location_id == location_id,
                LocationInventoryLedger.variant_id.in_(variant_ids),
            )
            .group_by(LocationInventoryLedger.variant_id)
        ).all()
        location_stock_by_variant = {variant_id: int(stock) for variant_id, stock in location_rows}

    items = [
        VariantOut(
            id=row["id"],
            product_id=row["product_id"],
            product_name=row["product_name"],
            business_id=row.get("business_id") or biz.id,
            size=row["size"],
            label=row["label"],
            sku=row["sku"],
            image_url=row["image_url"],
            reorder_level=int(row.get("reorder_level") or 0),
            cost_price=float(row["cost_price"]) if row["cost_price"] is not None else None,
            selling_price=float(row["selling_price"]) if row["selling_price"] is not None else None,
            is_published=bool(row["is_published"]) if has_variant_is_published else False,
            stock=stock_by_variant.get(row["id"], 0),
            location_stock=location_stock_by_variant.get(row["id"]) if location_id else None,
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
    "/{product_id}/variants/{variant_id}",
    response_model=VariantUpdateOut,
    summary="Update product variant details",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def update_variant(
    product_id: str,
    variant_id: str,
    payload: VariantUpdateIn,
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

    fields_set = payload.model_fields_set
    if "sku" in fields_set and payload.sku:
        sku_exists = db.execute(
            select(ProductVariant.id).where(
                ProductVariant.business_id == biz.id,
                func.lower(ProductVariant.sku) == payload.sku.lower(),
                ProductVariant.id != variant.id,
            )
        ).scalar_one_or_none()
        if sku_exists:
            raise HTTPException(status_code=400, detail="SKU already exists")

    previous_state = {
        "size": variant.size,
        "label": variant.label,
        "sku": variant.sku,
        "image_url": variant.image_url,
        "reorder_level": variant.reorder_level,
        "cost_price": float(variant.cost_price) if variant.cost_price is not None else None,
        "selling_price": float(variant.selling_price) if variant.selling_price is not None else None,
    }

    if "size" in fields_set:
        variant.size = payload.size or variant.size
    if "label" in fields_set:
        variant.label = payload.label
    if "sku" in fields_set:
        variant.sku = payload.sku
    if "image_url" in fields_set:
        variant.image_url = payload.image_url
    if "reorder_level" in fields_set and payload.reorder_level is not None:
        variant.reorder_level = payload.reorder_level
    if "cost_price" in fields_set:
        variant.cost_price = payload.cost_price
    if "selling_price" in fields_set:
        variant.selling_price = payload.selling_price

    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="product.variant.update",
        target_type="product_variant",
        target_id=variant.id,
        metadata_json={
            "product_id": product.id,
            "previous": previous_state,
            "next": {
                "size": variant.size,
                "label": variant.label,
                "sku": variant.sku,
                "image_url": variant.image_url,
                "reorder_level": variant.reorder_level,
                "cost_price": float(variant.cost_price) if variant.cost_price is not None else None,
                "selling_price": float(variant.selling_price) if variant.selling_price is not None else None,
            },
        },
    )
    db.commit()
    return VariantUpdateOut(
        id=variant.id,
        product_id=product.id,
        image_url=variant.image_url,
        sku=variant.sku,
        selling_price=float(variant.selling_price) if variant.selling_price is not None else None,
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
