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


class SaleQuote(BaseModel):
    items: List[SaleItemIn]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
    currency: str


class SaleQuoteLineOut(BaseModel):
    variant_id: str
    qty: int
    unit_price: float
    line_total: float
    available_stock: int | None = None
    errors: list[str] = Field(default_factory=list)
    is_valid: bool


class SaleQuoteOut(BaseModel):
    total: float
    currency: str
    items: list[SaleQuoteLineOut]
    errors: list[str] = Field(default_factory=list)
    is_valid: bool


class SaleOut(BaseModel):
    id: str
    kind: SaleKind
    parent_sale_id: Optional[str] = None
    payment_method: PaymentMethod
    channel: SalesChannel
    note: Optional[str] = None
    currency: str
    total_amount: float
    created_at: datetime


class SaleListOut(BaseModel):
    pagination: PaginationMeta
    base_currency: str
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


class SaleRefundOptionOut(BaseModel):
    variant_id: str
    product_id: str
    product_name: str
    size: str
    label: str | None = None
    sku: str | None = None
    sold_qty: int
    refunded_qty: int
    refundable_qty: int
    default_unit_price: float | None = None


class SaleRefundOptionsOut(BaseModel):
    sale_id: str
    payment_method: PaymentMethod
    channel: SalesChannel
    items: list[SaleRefundOptionOut]
