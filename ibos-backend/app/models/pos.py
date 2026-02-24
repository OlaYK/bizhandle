from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PosShiftSession(Base):
    __tablename__ = "pos_shift_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    opened_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    closed_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0")
    closing_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    expected_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    cash_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_pos_shift_sessions_business_status_opened_at", "business_id", "status", "opened_at"),
        Index("ix_pos_shift_sessions_business_opened_by_status", "business_id", "opened_by_user_id", "status"),
    )


class OfflineOrderSyncEvent(Base):
    __tablename__ = "offline_order_sync_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    client_event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    order_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    conflict_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "client_event_id",
            name="uq_offline_order_sync_events_business_client_event",
        ),
        Index(
            "ix_offline_order_sync_events_business_status_created_at",
            "business_id",
            "status",
            "created_at",
        ),
    )
