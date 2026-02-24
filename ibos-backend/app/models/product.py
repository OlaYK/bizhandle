from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_products_business_created_at", "business_id", "created_at"),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), index=True)

    size: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 6by6ft
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # e.g., "Plain", "Pattern"
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    selling_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_product_variants_business_created_at", "business_id", "created_at"),
        Index("ix_product_variants_business_reorder_level", "business_id", "reorder_level"),
        Index(
            "ux_product_variants_business_sku_lower",
            "business_id",
            func.lower(sku),
            unique=True,
            postgresql_where=sku.isnot(None),
            sqlite_where=sku.isnot(None),
        ),
    )
