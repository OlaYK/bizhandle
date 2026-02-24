from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShippingProfile(Base):
    __tablename__ = "shipping_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, unique=True, index=True)
    default_origin_country: Mapped[str] = mapped_column(String(60), nullable=False, default="NG", server_default="NG")
    default_origin_state: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_origin_city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_origin_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    handling_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ShippingZone(Base):
    __tablename__ = "shipping_zones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipping_profiles.id"), nullable=False, index=True)
    zone_name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(60), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    postal_code_prefix: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_shipping_zones_profile_country_active", "profile_id", "country", "is_active"),
    )


class ShippingServiceRule(Base):
    __tablename__ = "shipping_service_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipping_profiles.id"), nullable=False, index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("shipping_zones.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="stub_carrier", server_default="stub_carrier")
    service_code: Mapped[str] = mapped_column(String(40), nullable=False)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    per_kg_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    min_eta_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    max_eta_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_shipping_service_rules_profile_zone_provider", "profile_id", "zone_id", "provider"),
    )


class CheckoutShippingSelection(Base):
    __tablename__ = "checkout_shipping_selections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    checkout_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("checkout_sessions.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    service_code: Mapped[str] = mapped_column(String(40), nullable=False)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False)
    zone_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    eta_min_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    eta_max_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), nullable=False, index=True)
    checkout_session_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("checkout_sessions.id"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    service_code: Mapped[str] = mapped_column(String(40), nullable=False)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="label_purchased",
        server_default="label_purchased",
    )
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    tracking_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    label_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(60), nullable=False)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_shipments_business_status_created_at", "business_id", "status", "created_at"),
    )


class ShipmentTrackingEvent(Base):
    __tablename__ = "shipment_tracking_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_shipment_tracking_events_shipment_event_time", "shipment_id", "event_time"),
    )
