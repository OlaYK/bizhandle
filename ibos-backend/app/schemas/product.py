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

    @field_validator("label", "sku")
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
                "reorder_level": 5,
                "cost_price": 50.0,
                "selling_price": 100.0,
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


class VariantCreateOut(BaseModel):
    id: str


class VariantOut(BaseModel):
    id: str
    product_id: str
    business_id: str
    size: str
    label: Optional[str] = None
    sku: Optional[str] = None
    reorder_level: int
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    is_published: bool = False
    stock: int
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
