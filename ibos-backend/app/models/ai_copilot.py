from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIFeatureSnapshot(Base):
    __tablename__ = "ai_feature_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    window_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    window_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    paid_orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    gross_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    refunds_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    refunds_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    net_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    expenses_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    refund_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    stockout_events_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    campaigns_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    campaigns_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    repeat_customers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "window_start_date",
            "window_end_date",
            name="uq_ai_feature_snapshots_business_window",
        ),
        Index(
            "ix_ai_feature_snapshots_business_window_end_created_at",
            "business_id",
            "window_end_date",
            "created_at",
        ),
    )


class AIGeneratedInsight(Base):
    __tablename__ = "ai_generated_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    feature_snapshot_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_feature_snapshots.id"),
        nullable=True,
        index=True,
    )
    insight_type: Mapped[str] = mapped_column(String(20), nullable=False)  # anomaly|urgency|opportunity
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", server_default="medium")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default="0.5")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    context_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_ai_generated_insights_business_status_created_at", "business_id", "status", "created_at"),
        Index("ix_ai_generated_insights_business_type_created_at", "business_id", "insight_type", "created_at"),
    )


class AIPrescriptiveAction(Base):
    __tablename__ = "ai_prescriptive_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    insight_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_generated_insights.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="proposed",
        server_default="proposed",
    )  # proposed|approved|rejected|executed
    decision_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    decided_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_ai_prescriptive_actions_business_status_created_at", "business_id", "status", "created_at"),
        Index("ix_ai_prescriptive_actions_insight_status", "insight_id", "status"),
    )


class AIRiskAlertConfig(Base):
    __tablename__ = "ai_risk_alert_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(default=True, server_default="1", nullable=False)
    refund_rate_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.10, server_default="0.1")
    stockout_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    cashflow_margin_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.15,
        server_default="0.15",
    )
    channels_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("business_id", name="uq_ai_risk_alert_configs_business"),
        Index("ix_ai_risk_alert_configs_business_updated_at", "business_id", "updated_at"),
    )


class AIRiskAlertEvent(Base):
    __tablename__ = "ai_risk_alert_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_risk_alert_configs.id"),
        nullable=True,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)  # cashflow_drop|stockout_risk|refund_spike
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", server_default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="triggered", server_default="triggered")
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    triggered_value: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    channels_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    context_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    acknowledged_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_ai_risk_alert_events_business_status_created_at", "business_id", "status", "created_at"),
        Index("ix_ai_risk_alert_events_business_type_created_at", "business_id", "alert_type", "created_at"),
    )


class AIGovernanceTrace(Base):
    __tablename__ = "ai_governance_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    trace_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    feature_snapshot_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_feature_snapshots.id"),
        nullable=True,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(String(3000), nullable=False)
    context_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    output_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_ai_governance_traces_business_created_at", "business_id", "created_at"),
        Index("ix_ai_governance_traces_business_type_created_at", "business_id", "trace_type", "created_at"),
    )
