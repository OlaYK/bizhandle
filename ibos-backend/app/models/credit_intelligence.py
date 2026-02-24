from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FinanceGuardrailPolicy(Base):
    __tablename__ = "finance_guardrail_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="1")
    margin_floor_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.15, server_default="0.15")
    margin_drop_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.08, server_default="0.08")
    expense_growth_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.25,
        server_default="0.25",
    )
    minimum_cash_buffer: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
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
        UniqueConstraint("business_id", name="uq_finance_guardrail_policies_business"),
        Index("ix_finance_guardrail_policies_business_updated_at", "business_id", "updated_at"),
    )
