from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("business_id", "code", name="uq_locations_business_code"),
        Index("ix_locations_business_active_created_at", "business_id", "is_active", "created_at"),
    )


class LocationMembershipScope(Base):
    __tablename__ = "location_membership_scopes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), nullable=False, index=True)
    membership_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("business_memberships.id"),
        nullable=False,
        index=True,
    )
    can_manage_inventory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("location_id", "membership_id", name="uq_location_membership_scope"),
    )


class LocationInventoryLedger(Base):
    __tablename__ = "location_inventory_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_variants.id"), nullable=False, index=True)
    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_location_inventory_ledger_business_location_variant_created_at",
            "business_id",
            "location_id",
            "variant_id",
            "created_at",
        ),
    )


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    from_location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), nullable=False, index=True)
    to_location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed", server_default="completed")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_stock_transfers_business_created_at", "business_id", "created_at"),
    )


class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    stock_transfer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stock_transfers.id"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_variants.id"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)


class OrderLocationAllocation(Base):
    __tablename__ = "order_location_allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey("locations.id"), nullable=False, index=True)
    allocated_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_order_location_allocations_business_allocated_at", "business_id", "allocated_at"),
    )
