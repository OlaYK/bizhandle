from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class ShippingZoneIn(BaseModel):
    zone_name: str = Field(min_length=2, max_length=120)
    country: str = Field(min_length=2, max_length=60)
    state: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    postal_code_prefix: str | None = Field(default=None, max_length=20)
    is_active: bool = True


class ShippingServiceRuleIn(BaseModel):
    provider: str = Field(default="stub_carrier", min_length=2, max_length=40)
    service_code: str = Field(min_length=2, max_length=40)
    service_name: str = Field(min_length=2, max_length=120)
    zone_name: str | None = Field(default=None, max_length=120)
    base_rate: Decimal = Field(default=0, ge=0)
    per_kg_rate: Decimal = Field(default=0, ge=0)
    min_eta_days: int = Field(default=1, ge=1, le=30)
    max_eta_days: int = Field(default=3, ge=1, le=60)
    is_active: bool = True


class ShippingSettingsUpsertIn(BaseModel):
    default_origin_country: str = Field(default="NG", min_length=2, max_length=60)
    default_origin_state: str | None = Field(default=None, max_length=120)
    default_origin_city: str | None = Field(default=None, max_length=120)
    default_origin_postal_code: str | None = Field(default=None, max_length=20)
    handling_fee: Decimal = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    zones: list[ShippingZoneIn] = Field(default_factory=list)
    service_rules: list[ShippingServiceRuleIn] = Field(default_factory=list)


class ShippingZoneOut(BaseModel):
    id: str
    zone_name: str
    country: str
    state: str | None = None
    city: str | None = None
    postal_code_prefix: str | None = None
    is_active: bool


class ShippingServiceRuleOut(BaseModel):
    id: str
    provider: str
    service_code: str
    service_name: str
    zone_name: str | None = None
    base_rate: float
    per_kg_rate: float
    min_eta_days: int
    max_eta_days: int
    is_active: bool


class ShippingSettingsOut(BaseModel):
    profile_id: str
    default_origin_country: str
    default_origin_state: str | None = None
    default_origin_city: str | None = None
    default_origin_postal_code: str | None = None
    handling_fee: float
    currency: str
    zones: list[ShippingZoneOut]
    service_rules: list[ShippingServiceRuleOut]
    updated_at: datetime


class ShippingQuoteIn(BaseModel):
    destination_country: str = Field(min_length=2, max_length=60)
    destination_state: str | None = Field(default=None, max_length=120)
    destination_city: str | None = Field(default=None, max_length=120)
    destination_postal_code: str | None = Field(default=None, max_length=20)
    total_weight_kg: float = Field(default=1.0, gt=0, le=1000)


class ShippingQuoteOptionOut(BaseModel):
    provider: str
    service_code: str
    service_name: str
    zone_name: str | None = None
    amount: float
    currency: str
    eta_min_days: int
    eta_max_days: int


class ShippingQuoteOut(BaseModel):
    checkout_session_token: str
    currency: str
    options: list[ShippingQuoteOptionOut]


class ShippingRateSelectIn(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    service_code: str = Field(min_length=2, max_length=40)
    service_name: str = Field(min_length=2, max_length=120)
    zone_name: str | None = Field(default=None, max_length=120)
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    eta_min_days: int = Field(default=1, ge=1, le=30)
    eta_max_days: int = Field(default=3, ge=1, le=60)


class ShippingRateSelectionOut(BaseModel):
    checkout_session_id: str
    provider: str
    service_code: str
    service_name: str
    zone_name: str | None = None
    amount: float
    currency: str
    eta_min_days: int
    eta_max_days: int
    updated_at: datetime


class ShipmentCreateIn(BaseModel):
    order_id: str
    checkout_session_id: str | None = None
    provider: str = Field(default="stub_carrier", min_length=2, max_length=40)
    service_code: str = Field(min_length=2, max_length=40)
    service_name: str = Field(min_length=2, max_length=120)
    shipping_cost: Decimal = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    recipient_name: str = Field(min_length=2, max_length=120)
    recipient_phone: str | None = Field(default=None, max_length=40)
    address_line1: str = Field(min_length=2, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=2, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str = Field(min_length=2, max_length=60)
    postal_code: str | None = Field(default=None, max_length=20)


class ShipmentTrackingEventOut(BaseModel):
    id: str
    status: str
    description: str | None = None
    event_time: datetime
    created_at: datetime


class ShipmentOut(BaseModel):
    id: str
    order_id: str
    checkout_session_id: str | None = None
    provider: str
    service_code: str
    service_name: str
    status: str
    shipping_cost: float
    currency: str
    tracking_number: str | None = None
    label_url: str | None = None
    recipient_name: str
    recipient_phone: str | None = None
    address_line1: str
    address_line2: str | None = None
    city: str
    state: str | None = None
    country: str
    postal_code: str | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    tracking_events: list[ShipmentTrackingEventOut] = Field(default_factory=list)


class ShipmentListOut(BaseModel):
    items: list[ShipmentOut]
    pagination: PaginationMeta
    order_id: str | None = None
    status: str | None = None


class ShipmentTrackingSyncOut(BaseModel):
    shipment_id: str
    shipment_status: str
    order_id: str
    order_status: str
    tracking_events_added: int


class DispatchOut(BaseModel):
    ok: bool = True

    model_config = ConfigDict(
        json_schema_extra={"example": {"ok": True}}
    )
