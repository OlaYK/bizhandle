from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta
from app.schemas.sales import PaymentMethod, SalesChannel


class CheckoutSessionItemIn(BaseModel):
    variant_id: str
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)


class CheckoutSessionCreateIn(BaseModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    customer_id: Optional[str] = None
    payment_method: PaymentMethod = "transfer"
    channel: SalesChannel = "instagram"
    note: Optional[str] = None
    success_redirect_url: Optional[str] = None
    cancel_redirect_url: Optional[str] = None
    expires_in_minutes: int = Field(default=60, ge=5, le=10080)
    items: list[CheckoutSessionItemIn] = Field(min_length=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "currency": "USD",
                "payment_method": "transfer",
                "channel": "instagram",
                "note": "Promo checkout session",
                "expires_in_minutes": 120,
                "items": [{"variant_id": "variant-id", "qty": 2, "unit_price": 120.0}],
            }
        }
    )


class CheckoutSessionItemOut(BaseModel):
    variant_id: str
    qty: int
    unit_price: float
    line_total: float


class CheckoutSessionCreateOut(BaseModel):
    id: str
    session_token: str
    checkout_url: str
    status: str
    payment_provider: str
    payment_reference: str | None = None
    payment_checkout_url: str | None = None
    total_amount: float
    expires_at: datetime


class CheckoutSessionOut(BaseModel):
    id: str
    session_token: str
    status: str
    currency: str
    customer_id: str | None = None
    payment_method: PaymentMethod
    channel: SalesChannel
    total_amount: float
    payment_provider: str
    payment_reference: str | None = None
    payment_checkout_url: str | None = None
    order_id: str | None = None
    order_status: str | None = None
    sale_id: str | None = None
    has_sale: bool = False
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class CheckoutSessionListOut(BaseModel):
    items: list[CheckoutSessionOut]
    pagination: PaginationMeta
    status: str | None = None
    payment_provider: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class CheckoutSessionPublicOut(BaseModel):
    session_token: str
    status: str
    currency: str
    payment_method: PaymentMethod
    channel: SalesChannel
    note: str | None = None
    total_amount: float
    expires_at: datetime
    items: list[CheckoutSessionItemOut]


class CheckoutSessionPlaceOrderIn(BaseModel):
    customer_id: str | None = None
    payment_method: PaymentMethod | None = None
    note: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "customer-id",
                "payment_method": "transfer",
                "note": "Proceeding to payment",
            }
        }
    )


class CheckoutSessionPlaceOrderOut(BaseModel):
    checkout_session_id: str
    checkout_session_token: str
    checkout_status: str
    order_id: str
    order_status: str
    total_amount: float


class CheckoutSessionRetryPaymentOut(BaseModel):
    checkout_session_id: str
    checkout_session_token: str
    checkout_status: str
    payment_provider: str
    payment_reference: str
    payment_checkout_url: str | None = None
    expires_at: datetime


class CheckoutWebhookEventIn(BaseModel):
    event_id: str
    event_type: str
    payment_reference: str | None = None
    session_token: str | None = None
    status: str | None = None
    amount: float | None = None
    metadata: dict[str, object] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "evt_001",
                "event_type": "payment.succeeded",
                "payment_reference": "stub-abc123",
                "session_token": "checkout-token",
                "status": "success",
                "amount": 250.0,
                "metadata": {"provider": "stub"},
            }
        }
    )


class CheckoutWebhookOut(BaseModel):
    ok: bool
    provider: str
    checkout_session_id: str | None = None
    checkout_session_status: str | None = None
    order_id: str | None = None
    order_status: str | None = None
    duplicate: bool = False


class CheckoutPaymentsSummaryOut(BaseModel):
    total_sessions: int
    open_count: int
    pending_payment_count: int
    failed_count: int
    paid_count: int
    expired_count: int
    paid_amount_total: float
    reconciled_count: int
    unreconciled_count: int
    start_date: date | None = None
    end_date: date | None = None
