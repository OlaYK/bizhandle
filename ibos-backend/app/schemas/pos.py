from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.sales import PaymentMethod, SalesChannel

ALLOWED_OFFLINE_CONFLICT_POLICIES = {"reject_conflict", "adjust_to_available"}


class PosOfflineOrderItemIn(BaseModel):
    variant_id: str
    qty: int = Field(ge=1, le=100000)
    unit_price: Decimal = Field(gt=0)


class PosOfflineOrderIn(BaseModel):
    client_event_id: str = Field(min_length=4, max_length=120)
    customer_id: str | None = None
    payment_method: PaymentMethod
    channel: SalesChannel
    note: str | None = Field(default=None, max_length=255)
    created_at: datetime | None = None
    items: list[PosOfflineOrderItemIn]

    @field_validator("client_event_id", "customer_id", "note")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class PosOfflineSyncIn(BaseModel):
    conflict_policy: str = "reject_conflict"
    orders: list[PosOfflineOrderIn]

    @field_validator("conflict_policy")
    @classmethod
    def _normalize_policy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_OFFLINE_CONFLICT_POLICIES:
            allowed = ", ".join(sorted(ALLOWED_OFFLINE_CONFLICT_POLICIES))
            raise ValueError(f"Invalid conflict policy. Allowed: {allowed}")
        return normalized

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conflict_policy": "adjust_to_available",
                "orders": [
                    {
                        "client_event_id": "pos-evt-001",
                        "payment_method": "cash",
                        "channel": "walk-in",
                        "items": [{"variant_id": "variant-id", "qty": 2, "unit_price": 100}],
                    }
                ],
            }
        }
    )


class PosOfflineSyncResultOut(BaseModel):
    client_event_id: str
    status: str
    order_id: str | None = None
    conflict_code: str | None = None
    note: str | None = None


class PosOfflineSyncOut(BaseModel):
    processed: int
    created: int
    conflicted: int
    duplicate: int
    results: list[PosOfflineSyncResultOut]


class PosShiftOpenIn(BaseModel):
    opening_cash: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=255)

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class PosShiftCloseIn(BaseModel):
    closing_cash: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=255)

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class PosShiftOut(BaseModel):
    id: str
    status: str
    opening_cash: float
    closing_cash: float | None = None
    expected_cash: float | None = None
    cash_difference: float | None = None
    opened_by_user_id: str
    closed_by_user_id: str | None = None
    note: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None


class PosShiftCurrentOut(BaseModel):
    shift: Optional[PosShiftOut] = None
