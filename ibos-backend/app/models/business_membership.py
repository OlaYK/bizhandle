from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BusinessMembership(Base):
    __tablename__ = "business_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner", server_default="owner")
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ux_business_memberships_business_user", "business_id", "user_id", unique=True),
        Index(
            "ix_business_memberships_user_active_created_at",
            "user_id",
            "is_active",
            "created_at",
        ),
    )
