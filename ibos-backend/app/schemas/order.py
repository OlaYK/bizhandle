from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta
from app.schemas.sales import PaymentMethod, SalesChannel

OrderStatus = str
ALLOWED_ORDER_STATUSES = {
    "pending",
    "paid",
    "processing",
    "fulfilled",
    "cancelled",
    "refunded",
}


class OrderItemIn(BaseModel):
    variant_id: str
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: Optional[str] = None
    payment_method: PaymentMethod
    channel: SalesChannel
    note: Optional[str] = None
    items: list[OrderItemIn] = Field(min_length=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "customer-id-here",
                "payment_method": "cash",
                "channel": "walk-in",
                "note": "Customer will pay on pickup",
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


class OrderStatusUpdateIn(BaseModel):
    status: str
    note: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "paid",
                "note": "Payment confirmed",
            }
        }
    )


class OrderCreateOut(BaseModel):
    id: str
    total: float
    status: str
    sale_id: str | None = None


class OrderOut(BaseModel):
    id: str
    customer_id: str | None = None
    payment_method: PaymentMethod
    channel: SalesChannel
    status: str
    total_amount: float
    sale_id: str | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class OrderListOut(BaseModel):
    pagination: PaginationMeta
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    channel: SalesChannel | None = None
    customer_id: str | None = None
    items: list[OrderOut]
