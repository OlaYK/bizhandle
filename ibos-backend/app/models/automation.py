from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    trigger_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="outbox_event",
        server_default="outbox_event",
    )
    trigger_event_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="*",
        server_default="*",
        index=True,
    )
    conditions_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    actions_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    template_key: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    run_limit_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=120, server_default="120")
    reentry_cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        server_default="300",
    )
    rollback_on_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_automation_rules_business_name"),
        Index(
            "ix_automation_rules_business_status_updated_at",
            "business_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_automation_rules_business_trigger_status",
            "business_id",
            "trigger_event_type",
            "status",
        ),
    )


class AutomationRuleRun(Base):
    __tablename__ = "automation_rule_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("automation_rules.id"), nullable=False, index=True)
    trigger_event_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("integration_outbox_events.id"),
        nullable=True,
        index=True,
    )
    trigger_event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    trigger_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trigger_fingerprint: Mapped[Optional[str]] = mapped_column(String(160), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    blocked_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    steps_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    steps_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    steps_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("rule_id", "trigger_event_id", name="uq_automation_rule_runs_rule_trigger_event"),
        Index("ix_automation_rule_runs_rule_created_at", "rule_id", "created_at"),
        Index(
            "ix_automation_rule_runs_business_status_created_at",
            "business_id",
            "status",
            "created_at",
        ),
    )


class AutomationRuleStep(Base):
    __tablename__ = "automation_rule_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    rule_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("automation_rule_runs.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("automation_rules.id"), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_automation_rule_steps_run_step", "rule_run_id", "step_index"),
        Index("ix_automation_rule_steps_business_created_at", "business_id", "created_at"),
    )


class AutomationTask(Base):
    __tablename__ = "automation_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    rule_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("automation_rule_runs.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    assignee_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_automation_tasks_business_status_created_at", "business_id", "status", "created_at"),
    )


class AutomationDiscount(Base):
    __tablename__ = "automation_discounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    rule_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("automation_rule_runs.id"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="percentage", server_default="percentage")
    value: Mapped[float] = mapped_column(Float, nullable=False)
    max_redemptions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_customer_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("customers.id"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("business_id", "code", name="uq_automation_discounts_business_code"),
        Index(
            "ix_automation_discounts_business_status_created_at",
            "business_id",
            "status",
            "created_at",
        ),
    )
