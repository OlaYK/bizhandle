from datetime import datetime, date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


PaymentMethod = Literal["cash", "transfer", "pos"]
SalesChannel = Literal["whatsapp", "instagram", "walk-in"]
SaleKind = Literal["sale", "refund"]

class SaleItemIn(BaseModel):
    variant_id: str
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)

class SaleCreate(BaseModel):
    payment_method: PaymentMethod
    channel: SalesChannel
    note: Optional[str] = None
    items: List[SaleItemIn]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_method": "cash",
                "channel": "walk-in",
                "items": [
                    {
                        "variant_id": "variant-id-here",
                        "qty": 2,
                        "unit_price": 120.0,
                    }
                ],
            }
        }
    )


class SaleCreateOut(BaseModel):
    id: str
    total: float


class SaleOut(BaseModel):
    id: str
    kind: SaleKind
    parent_sale_id: Optional[str] = None
    payment_method: PaymentMethod
    channel: SalesChannel
    note: Optional[str] = None
    total_amount: float
    created_at: datetime


class SaleListOut(BaseModel):
    pagination: PaginationMeta
    start_date: date | None = None
    end_date: date | None = None
    items: list[SaleOut]


class RefundItemIn(BaseModel):
    variant_id: str
    qty: int = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)


class RefundCreate(BaseModel):
    payment_method: PaymentMethod | None = None
    channel: SalesChannel | None = None
    note: str | None = None
    items: list[RefundItemIn]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_method": "transfer",
                "channel": "instagram",
                "note": "Customer returned wrong size",
                "items": [{"variant_id": "variant-id-here", "qty": 1, "unit_price": 120.0}],
            }
        }
    )
