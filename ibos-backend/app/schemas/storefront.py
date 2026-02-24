from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.schemas.common import PaginationMeta


class StorefrontConfigUpsertIn(BaseModel):
    slug: str
    display_name: str
    tagline: str | None = None
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_og_image_url: str | None = None
    logo_url: str | None = None
    accent_color: str | None = None
    hero_image_url: str | None = None
    support_email: EmailStr | None = None
    support_phone: str | None = None
    policy_shipping: str | None = None
    policy_returns: str | None = None
    policy_privacy: str | None = None
    custom_domain: str | None = None
    is_published: bool = False

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) < 3 or len(cleaned) > 80:
            raise ValueError("slug must be between 3 and 80 characters")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if cleaned[0] == "-" or cleaned[-1] == "-" or any(ch not in allowed for ch in cleaned):
            raise ValueError("slug may only contain lowercase letters, numbers, and hyphens")
        if "--" in cleaned:
            raise ValueError("slug cannot contain consecutive hyphens")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name is required")
        return cleaned

    @field_validator(
        "tagline",
        "description",
        "seo_title",
        "seo_description",
        "seo_og_image_url",
        "logo_url",
        "accent_color",
        "hero_image_url",
        "support_phone",
        "policy_shipping",
        "policy_returns",
        "policy_privacy",
        "custom_domain",
    )
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("accent_color")
    @classmethod
    def validate_accent_color(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        candidate = value.strip().lower()
        if len(candidate) != 7 or not candidate.startswith("#"):
            raise ValueError("accent_color must be a hex value like #16a34a")
        hex_chars = set("0123456789abcdef")
        if any(ch not in hex_chars for ch in candidate[1:]):
            raise ValueError("accent_color must be a valid hex value")
        return candidate

    @field_validator("seo_title")
    @classmethod
    def validate_seo_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if len(value) > 160:
            raise ValueError("seo_title cannot exceed 160 characters")
        return value

    @field_validator("seo_description")
    @classmethod
    def validate_seo_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if len(value) > 320:
            raise ValueError("seo_description cannot exceed 320 characters")
        return value

    @field_validator("custom_domain")
    @classmethod
    def validate_custom_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        lowered = value.lower()
        if "://" in lowered:
            raise ValueError("custom_domain must be a hostname without protocol")
        if "/" in lowered or " " in lowered:
            raise ValueError("custom_domain must be a valid hostname")
        if "." not in lowered:
            raise ValueError("custom_domain must include a valid domain suffix")
        return lowered

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slug": "ankara-house",
                "display_name": "Ankara House",
                "tagline": "Premium fabrics for modern homes",
                "description": "Shop curated fabric collections and accessories.",
                "accent_color": "#16a34a",
                "policy_shipping": "Delivery in 1-3 business days.",
                "policy_returns": "Returns accepted within 7 days for unused items.",
                "policy_privacy": "Customer data is processed for order fulfillment only.",
                "is_published": True,
            }
        }
    )


class StorefrontConfigOut(BaseModel):
    id: str
    business_id: str
    slug: str
    display_name: str
    tagline: str | None = None
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_og_image_url: str | None = None
    logo_url: str | None = None
    accent_color: str | None = None
    hero_image_url: str | None = None
    support_email: EmailStr | None = None
    support_phone: str | None = None
    policy_shipping: str | None = None
    policy_returns: str | None = None
    policy_privacy: str | None = None
    custom_domain: str | None = None
    domain_verification_status: str
    domain_verification_token: str | None = None
    domain_last_checked_at: datetime | None = None
    domain_verified_at: datetime | None = None
    is_published: bool
    created_at: datetime
    updated_at: datetime


class PublicStorefrontOut(BaseModel):
    slug: str
    display_name: str
    tagline: str | None = None
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_og_image_url: str | None = None
    logo_url: str | None = None
    accent_color: str | None = None
    hero_image_url: str | None = None
    support_email: EmailStr | None = None
    support_phone: str | None = None
    policy_shipping: str | None = None
    policy_returns: str | None = None
    policy_privacy: str | None = None


class PublicStorefrontProductOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    starting_price: float | None = None
    published_variant_count: int


class PublicStorefrontProductListOut(BaseModel):
    items: list[PublicStorefrontProductOut]
    pagination: PaginationMeta
    q: str | None = None
    category: str | None = None


class PublicStorefrontVariantOut(BaseModel):
    id: str
    size: str
    label: str | None = None
    sku: str | None = None
    selling_price: float | None = None


class PublicStorefrontProductDetailOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    description: str | None = None
    variants: list[PublicStorefrontVariantOut]


class StorefrontDomainChallengeOut(BaseModel):
    custom_domain: str
    verification_status: str
    txt_record_name: str
    txt_record_value: str
    domain_last_checked_at: datetime | None = None


class StorefrontDomainVerifyIn(BaseModel):
    verification_token: str

    @field_validator("verification_token")
    @classmethod
    def validate_verification_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("verification_token is required")
        return cleaned


class StorefrontDomainStatusOut(BaseModel):
    custom_domain: str | None = None
    verification_status: str
    txt_record_name: str | None = None
    txt_record_value: str | None = None
    domain_last_checked_at: datetime | None = None
    domain_verified_at: datetime | None = None
