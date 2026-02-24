from datetime import datetime
from decimal import Decimal
from typing import Optional

from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    session_token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
        server_default="open",
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    customer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="transfer", server_default="transfer")
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="instagram", server_default="instagram")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    success_redirect_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cancel_redirect_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    payment_provider: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="stub",
        server_default="stub",
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    payment_checkout_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_checkout_sessions_business_status_created_at", "business_id", "status", "created_at"),
        Index("ix_checkout_sessions_business_expires_at", "business_id", "expires_at"),
    )


class CheckoutSessionItem(Base):
    __tablename__ = "checkout_session_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    checkout_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("checkout_sessions.id"),
        index=True,
    )
    variant_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_variants.id"), index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class CheckoutWebhookEvent(Base):
    __tablename__ = "checkout_webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    checkout_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("checkout_sessions.id"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_checkout_webhook_events_checkout_provider", "checkout_session_id", "provider"),
        Index("ix_checkout_webhook_events_provider_created_at", "provider", "created_at"),
    )
