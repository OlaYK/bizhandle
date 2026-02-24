from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
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


class InvoiceTemplate(Base):
    __tablename__ = "invoice_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    brand_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    footer_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_invoice_templates_business_status_created_at", "business_id", "status", "created_at"),
        Index("ix_invoice_templates_business_default_updated_at", "business_id", "is_default", "updated_at"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("1.000000"), server_default="1")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )
    amount_paid_base: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    template_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("invoice_templates.id"),
        nullable=True,
        index=True,
    )
    reminder_policy_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_invoices_business_status_created_at", "business_id", "status", "created_at"),
        Index("ix_invoices_business_due_date", "business_id", "due_date"),
        Index("ix_invoices_business_next_reminder", "business_id", "next_reminder_at"),
    )


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_invoice_payments_business_paid_at", "business_id", "paid_at"),
        Index("ix_invoice_payments_invoice_created_at", "invoice_id", "created_at"),
    )


class InvoiceInstallment(Base):
    __tablename__ = "invoice_installments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_invoice_installments_invoice_due_date", "invoice_id", "due_date"),
        Index("ix_invoice_installments_business_status_due_date", "business_id", "status", "due_date"),
    )


class InvoiceEvent(Base):
    __tablename__ = "invoice_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), index=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_invoice_events_business_created_at", "business_id", "created_at"),
        Index("ix_invoice_events_invoice_event_type_created_at", "invoice_id", "event_type", "created_at"),
    )
