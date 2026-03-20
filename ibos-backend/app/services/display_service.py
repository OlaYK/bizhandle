from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.money import ZERO_MONEY, to_money
from app.models.customer import Customer
from app.models.inventory import InventoryLedger
from app.models.location import Location, OrderLocationAllocation
from app.models.product import Product, ProductVariant


@dataclass(frozen=True)
class VariantDisplay:
    variant_id: str
    product_id: str
    product_name: str
    size: str
    label: str | None
    sku: str | None
    image_url: str | None
    selling_price: Decimal | None
    reorder_level: int


@dataclass(frozen=True)
class ProductDefaultVariantDisplay:
    variant_id: str
    sku: str | None
    image_url: str | None
    selling_price: Decimal | None
    stock: int


@dataclass(frozen=True)
class OrderAllocationDisplay:
    allocation_id: str
    order_id: str
    location_id: str
    location_name: str | None
    allocated_at: datetime


def get_customer_name_map(
    db: Session,
    *,
    business_id: str,
    customer_ids: list[str | None],
) -> dict[str, str]:
    normalized_ids = sorted({item for item in customer_ids if item})
    if not normalized_ids:
        return {}
    rows = db.execute(
        select(Customer.id, Customer.name).where(
            Customer.business_id == business_id,
            Customer.id.in_(normalized_ids),
        )
    ).all()
    return {customer_id: name for customer_id, name in rows}


def get_location_name_map(
    db: Session,
    *,
    business_id: str,
    location_ids: list[str | None],
) -> dict[str, str]:
    normalized_ids = sorted({item for item in location_ids if item})
    if not normalized_ids:
        return {}
    rows = db.execute(
        select(Location.id, Location.name).where(
            Location.business_id == business_id,
            Location.id.in_(normalized_ids),
        )
    ).all()
    return {location_id: name for location_id, name in rows}


def get_variant_display_map(
    db: Session,
    *,
    business_id: str,
    variant_ids: list[str],
) -> dict[str, VariantDisplay]:
    normalized_ids = sorted({item for item in variant_ids if item})
    if not normalized_ids:
        return {}
    rows = db.execute(
        select(
            ProductVariant.id,
            ProductVariant.product_id,
            Product.name,
            ProductVariant.size,
            ProductVariant.label,
            ProductVariant.sku,
            ProductVariant.image_url,
            ProductVariant.selling_price,
            ProductVariant.reorder_level,
        )
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            ProductVariant.business_id == business_id,
            ProductVariant.id.in_(normalized_ids),
        )
    ).all()
    return {
        variant_id: VariantDisplay(
            variant_id=variant_id,
            product_id=product_id,
            product_name=product_name,
            size=size,
            label=label,
            sku=sku,
            image_url=image_url,
            selling_price=to_money(selling_price) if selling_price is not None else None,
            reorder_level=int(reorder_level or 0),
        )
        for variant_id, product_id, product_name, size, label, sku, image_url, selling_price, reorder_level in rows
    }


def get_product_default_variant_map(
    db: Session,
    *,
    business_id: str,
    product_ids: list[str],
) -> dict[str, ProductDefaultVariantDisplay]:
    normalized_ids = sorted({item for item in product_ids if item})
    if not normalized_ids:
        return {}

    rows = db.execute(
        select(
            ProductVariant.id,
            ProductVariant.product_id,
            ProductVariant.sku,
            ProductVariant.image_url,
            ProductVariant.selling_price,
            ProductVariant.created_at,
        )
        .where(
            ProductVariant.business_id == business_id,
            ProductVariant.product_id.in_(normalized_ids),
        )
        .order_by(ProductVariant.product_id.asc(), ProductVariant.created_at.asc(), ProductVariant.id.asc())
    ).all()
    if not rows:
        return {}

    variant_ids = [variant_id for variant_id, _product_id, _sku, _image_url, _selling_price, _created_at in rows]
    stock_rows = db.execute(
        select(
            InventoryLedger.variant_id,
            func.coalesce(func.sum(InventoryLedger.qty_delta), 0),
        )
        .where(
            InventoryLedger.business_id == business_id,
            InventoryLedger.variant_id.in_(variant_ids),
        )
        .group_by(InventoryLedger.variant_id)
    ).all()
    stock_by_variant = {variant_id: int(stock) for variant_id, stock in stock_rows}

    defaults: dict[str, ProductDefaultVariantDisplay] = {}
    fallback_defaults: dict[str, ProductDefaultVariantDisplay] = {}
    for variant_id, product_id, sku, image_url, selling_price, _created_at in rows:
        candidate = ProductDefaultVariantDisplay(
            variant_id=variant_id,
            sku=sku,
            image_url=image_url,
            selling_price=to_money(selling_price) if selling_price is not None else None,
            stock=stock_by_variant.get(variant_id, 0),
        )
        fallback_defaults.setdefault(product_id, candidate)
        if candidate.stock > 0 and product_id not in defaults:
            defaults[product_id] = candidate
    for product_id, candidate in fallback_defaults.items():
        defaults.setdefault(product_id, candidate)
    return defaults


def get_variant_stock_map(
    db: Session,
    *,
    business_id: str,
    variant_ids: list[str],
) -> dict[str, int]:
    normalized_ids = sorted({item for item in variant_ids if item})
    if not normalized_ids:
        return {}
    rows = db.execute(
        select(
            InventoryLedger.variant_id,
            func.coalesce(func.sum(InventoryLedger.qty_delta), ZERO_MONEY),
        )
        .where(
            InventoryLedger.business_id == business_id,
            InventoryLedger.variant_id.in_(normalized_ids),
        )
        .group_by(InventoryLedger.variant_id)
    ).all()
    return {variant_id: int(to_money(stock or 0)) for variant_id, stock in rows}


def get_order_allocation_map(
    db: Session,
    *,
    business_id: str,
    order_ids: list[str],
) -> dict[str, OrderAllocationDisplay]:
    normalized_ids = sorted({item for item in order_ids if item})
    if not normalized_ids:
        return {}
    rows = db.execute(
        select(
            OrderLocationAllocation.id,
            OrderLocationAllocation.order_id,
            OrderLocationAllocation.location_id,
            OrderLocationAllocation.allocated_at,
            Location.name,
        )
        .join(Location, Location.id == OrderLocationAllocation.location_id)
        .where(
            OrderLocationAllocation.business_id == business_id,
            OrderLocationAllocation.order_id.in_(normalized_ids),
        )
    ).all()
    return {
        order_id: OrderAllocationDisplay(
            allocation_id=allocation_id,
            order_id=order_id,
            location_id=location_id,
            location_name=location_name,
            allocated_at=allocated_at,
        )
        for allocation_id, order_id, location_id, allocated_at, location_name in rows
    }
