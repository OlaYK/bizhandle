from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PaginationMeta


class StockIn(BaseModel):
    variant_id: str
    qty: int = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "variant_id": "variant-id-here",
                "qty": 20,
                "unit_cost": 45.0,
            }
        }
    )


class StockOut(BaseModel):
    ok: bool = True


class StockLevelOut(BaseModel):
    variant_id: str
    stock: int


class InventoryLedgerEntryOut(BaseModel):
    id: str
    variant_id: str
    qty_delta: int
    reason: str
    reference_id: str | None = None
    note: str | None = None
    unit_cost: float | None = None
    created_at: datetime


class StockAdjustIn(BaseModel):
    variant_id: str
    qty_delta: int = Field(
        ..., description="Positive adds stock, negative removes stock. Cannot be zero."
    )
    reason: str = Field(..., min_length=3, max_length=50)
    note: str | None = Field(default=None, max_length=255)
    unit_cost: Decimal | None = Field(default=None, gt=0)

    @field_validator("qty_delta")
    @classmethod
    def validate_non_zero_qty_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("qty_delta cannot be zero")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "variant_id": "variant-id-here",
                "qty_delta": -2,
                "reason": "damaged_stock",
                "note": "2 pieces damaged during packaging",
                "unit_cost": 45.0,
            }
        }
    )


class LowStockVariantOut(BaseModel):
    variant_id: str
    product_id: str
    product_name: str
    size: str
    label: str | None = None
    sku: str | None = None
    reorder_level: int
    stock: int


class InventoryLedgerListOut(BaseModel):
    items: list[InventoryLedgerEntryOut]
    pagination: PaginationMeta


class LowStockListOut(BaseModel):
    items: list[LowStockVariantOut]
    pagination: PaginationMeta
