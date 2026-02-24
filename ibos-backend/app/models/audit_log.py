from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_logs_business_created_at", "business_id", "created_at"),
        Index("ix_audit_logs_business_action_created_at", "business_id", "action", "created_at"),
        Index(
            "ix_audit_logs_business_actor_created_at",
            "business_id",
            "actor_user_id",
            "created_at",
        ),
    )


class AuditLogArchive(Base):
    __tablename__ = "audit_log_archives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    archived_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    cutoff_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    records_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    payload_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_log_archives_business_created_at", "business_id", "created_at"),
        Index(
            "ix_audit_log_archives_business_cutoff_date",
            "business_id",
            "cutoff_date",
        ),
    )
