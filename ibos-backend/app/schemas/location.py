from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import PaginationMeta


class LocationCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=30)


class LocationUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = Field(default=None, validation_alias=AliasChoices("is_active", "isActive"))

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "LocationUpdateIn":
        if self.name is None and self.is_active is None:
            raise ValueError("At least one field must be provided")
        return self

    model_config = ConfigDict(populate_by_name=True)


class LocationOut(BaseModel):
    id: str
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LocationListOut(BaseModel):
    items: list[LocationOut]
    pagination: PaginationMeta


class LocationMembershipScopeUpsertIn(BaseModel):
    can_manage_inventory: bool = False


class LocationMembershipScopeOut(BaseModel):
    id: str
    membership_id: str
    location_id: str
    can_manage_inventory: bool
    created_at: datetime


class LocationMembershipScopeListOut(BaseModel):
    items: list[LocationMembershipScopeOut]


class LocationStockInIn(BaseModel):
    variant_id: str
    qty: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class LocationStockAdjustIn(BaseModel):
    variant_id: str
    qty_delta: int = Field(...)
    reason: str = Field(min_length=3, max_length=50)
    note: str | None = Field(default=None, max_length=255)

    @field_validator("qty_delta")
    @classmethod
    def validate_non_zero_qty_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("qty_delta cannot be zero")
        return value


class LocationVariantStockOut(BaseModel):
    location_id: str
    variant_id: str
    stock: int


class LocationStockOverviewOut(BaseModel):
    variant_id: str
    by_location: list[LocationVariantStockOut]


class LocationTransferItemIn(BaseModel):
    variant_id: str
    qty: int = Field(gt=0)


class StockTransferCreateIn(BaseModel):
    from_location_id: str
    to_location_id: str
    note: str | None = Field(default=None, max_length=255)
    items: list[LocationTransferItemIn] = Field(min_length=1)


class StockTransferItemOut(BaseModel):
    variant_id: str
    qty: int


class StockTransferOut(BaseModel):
    id: str
    from_location_id: str
    to_location_id: str
    status: str
    note: str | None = None
    created_at: datetime
    items: list[StockTransferItemOut]


class StockTransferListOut(BaseModel):
    items: list[StockTransferOut]
    pagination: PaginationMeta


class LocationLowStockItemOut(BaseModel):
    location_id: str
    variant_id: str
    reorder_level: int
    stock: int


class LocationLowStockListOut(BaseModel):
    items: list[LocationLowStockItemOut]
    pagination: PaginationMeta


class OrderLocationAllocationIn(BaseModel):
    order_id: str
    location_id: str


class OrderLocationAllocationOut(BaseModel):
    id: str
    order_id: str
    location_id: str
    allocated_at: datetime
