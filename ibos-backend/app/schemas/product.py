from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PaginationMeta

class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Ankara Fabric",
                "category": "fabrics",
            }
        }
    )

class VariantCreate(BaseModel):
    size: str
    label: Optional[str] = None
    sku: Optional[str] = None
    image_url: Optional[str] = None
    reorder_level: int = Field(default=0, ge=0)
    cost_price: Optional[Decimal] = Field(default=None, gt=0)
    selling_price: Optional[Decimal] = Field(default=None, gt=0)

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("size is required")
        return cleaned

    @field_validator("label", "sku", "image_url")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "size": "6x6",
                "label": "Plain",
                "sku": "ANK-6X6-PLN",
                "image_url": "https://res.cloudinary.com/demo/image/upload/ankara.jpg",
                "reorder_level": 5,
                "cost_price": 50.0,
                "selling_price": 100.0,
            }
        }
    )


class VariantUpdateIn(BaseModel):
    size: str | None = None
    label: Optional[str] = None
    sku: Optional[str] = None
    image_url: Optional[str] = None
    reorder_level: int | None = Field(default=None, ge=0)
    cost_price: Optional[Decimal] = Field(default=None, gt=0)
    selling_price: Optional[Decimal] = Field(default=None, gt=0)

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("size cannot be empty")
        return cleaned

    @field_validator("label", "sku", "image_url")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "Pattern",
                "sku": "ANK-6X6-PTN",
                "image_url": "https://res.cloudinary.com/demo/image/upload/ankara-pattern.jpg",
                "selling_price": 115.0,
            }
        }
    )


class ProductCreateOut(BaseModel):
    id: str


class ProductOut(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    active: bool
    is_published: bool = False
    variant_count: int = 0
    default_variant_id: str | None = None
    default_sku: str | None = None
    default_selling_price: float | None = None
    default_stock: int | None = None
    default_image_url: str | None = None


class VariantCreateOut(BaseModel):
    id: str


class VariantUpdateOut(BaseModel):
    id: str
    product_id: str
    image_url: str | None = None
    sku: str | None = None
    selling_price: float | None = None


class VariantOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    business_id: str
    size: str
    label: Optional[str] = None
    sku: Optional[str] = None
    image_url: Optional[str] = None
    reorder_level: int
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    is_published: bool = False
    stock: int
    location_stock: int | None = None
    created_at: datetime


class ProductPublishIn(BaseModel):
    is_published: bool


class ProductPublishOut(BaseModel):
    id: str
    is_published: bool


class VariantPublishIn(BaseModel):
    is_published: bool


class VariantPublishOut(BaseModel):
    id: str
    product_id: str
    is_published: bool


class ProductListOut(BaseModel):
    items: list[ProductOut]
    pagination: PaginationMeta


class VariantListOut(BaseModel):
    items: list[VariantOut]
    pagination: PaginationMeta
