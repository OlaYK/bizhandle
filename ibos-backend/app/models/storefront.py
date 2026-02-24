from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StorefrontConfig(Base):
    __tablename__ = "storefront_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id"), index=True, unique=True
    )

    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    accent_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    hero_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    support_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    support_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    policy_shipping: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    policy_returns: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    policy_privacy: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    seo_title: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    seo_description: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    seo_og_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    custom_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    domain_verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_configured",
        server_default="not_configured",
    )
    domain_verification_token: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    domain_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    domain_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_storefront_configs_slug", "slug"),
        Index("ix_storefront_configs_business_slug", "business_id", "slug"),
        Index("ix_storefront_configs_custom_domain", "custom_domain"),
    )
