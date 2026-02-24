from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalyticsDailyMetric(Base):
    __tablename__ = "analytics_daily_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0")
    cogs: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0")
    expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0")
    gross_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    net_profit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0")
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    repeat_orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stockout_events_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "metric_date",
            "channel",
            name="uq_analytics_daily_metrics_business_date_channel",
        ),
        Index(
            "ix_analytics_daily_metrics_business_channel_metric_date",
            "business_id",
            "channel",
            "metric_date",
        ),
    )


class MarketingAttributionEvent(Base):
    __tablename__ = "marketing_attribution_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    medium: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    campaign_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    revenue_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_marketing_attribution_events_business_channel_event_time",
            "business_id",
            "channel",
            "event_time",
        ),
        Index(
            "ix_marketing_attribution_events_business_event_type_event_time",
            "business_id",
            "event_type",
            "event_time",
        ),
    )


class AnalyticsReportSchedule(Base):
    __tablename__ = "analytics_report_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="weekly", server_default="weekly")
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_analytics_report_schedules_business_status_next_run_at",
            "business_id",
            "status",
            "next_run_at",
        ),
    )
