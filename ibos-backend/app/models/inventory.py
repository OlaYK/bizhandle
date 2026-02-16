from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryLedger(Base):
    """
    One row per stock movement. Positive = stock in. Negative = stock out (sale/adjustment).
    """
    __tablename__ = "inventory_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    variant_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_variants.id"), index=True)

    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # "stock_in", "sale", "adjustment"
    reference_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # e.g., sale_id
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)  # for COGS logic later

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_inventory_ledger_business_created_at", "business_id", "created_at"),
        Index(
            "ix_inventory_ledger_business_variant_created_at",
            "business_id",
            "variant_id",
            "created_at",
        ),
    )
