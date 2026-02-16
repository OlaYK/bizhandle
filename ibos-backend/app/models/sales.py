from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)

    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)  # cash/transfer/pos
    channel: Mapped[str] = mapped_column(String(30), nullable=False)         # whatsapp/instagram/walk-in
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="sale", server_default="sale")
    parent_sale_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sales.id"), nullable=True, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_sales_business_created_at", "business_id", "created_at"),
        Index("ix_sales_business_kind_created_at", "business_id", "kind", "created_at"),
    )


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sale_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales.id"), index=True)
    variant_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_variants.id"), index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
