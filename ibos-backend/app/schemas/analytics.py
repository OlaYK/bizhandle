from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AnalyticsMartRefreshOut(BaseModel):
    start_date: date
    end_date: date
    rows_refreshed: int


class ChannelProfitabilityItemOut(BaseModel):
    channel: str
    revenue: float
    cogs: float
    expenses: float
    gross_profit: float
    net_profit: float
    orders_count: int
    margin_pct: float


class ChannelProfitabilityOut(BaseModel):
    start_date: date
    end_date: date
    items: list[ChannelProfitabilityItemOut]


class CohortRetentionItemOut(BaseModel):
    cohort_month: str
    total_customers: int
    retained_customers: int
    retention_rate: float


class CohortRetentionOut(BaseModel):
    months_after: int
    items: list[CohortRetentionItemOut]


class InventoryAgingItemOut(BaseModel):
    variant_id: str
    bucket: str
    stock: int
    estimated_value: float
    days_since_last_movement: int | None = None


class InventoryAgingOut(BaseModel):
    as_of_date: date
    stockout_count: int
    total_estimated_inventory_value: float
    items: list[InventoryAgingItemOut]


class MarketingAttributionEventIn(BaseModel):
    event_type: str = Field(min_length=2, max_length=40)
    channel: str = Field(min_length=2, max_length=40)
    source: str | None = Field(default=None, max_length=80)
    medium: str | None = Field(default=None, max_length=80)
    campaign_name: str | None = Field(default=None, max_length=120)
    order_id: str | None = None
    revenue_amount: float = Field(default=0, ge=0)
    metadata_json: dict[str, Any] | None = None
    event_time: datetime | None = None

    @field_validator("event_type", "channel", "source", "medium", "campaign_name", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "order_conversion",
                "channel": "instagram",
                "source": "meta_ads",
                "medium": "cpc",
                "campaign_name": "Easter Promo",
                "order_id": "order-id",
                "revenue_amount": 120.0,
            }
        }
    )


class MarketingAttributionEventOut(BaseModel):
    id: str
    event_type: str
    channel: str
    source: str | None = None
    medium: str | None = None
    campaign_name: str | None = None
    order_id: str | None = None
    revenue_amount: float
    metadata_json: dict[str, Any] | None = None
    event_time: datetime
    created_at: datetime


class ReportExportOut(BaseModel):
    filename: str
    content_type: str
    row_count: int
    csv_content: str


class ReportScheduleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    report_type: str = Field(min_length=2, max_length=40)
    frequency: str = Field(default="weekly", min_length=3, max_length=20)
    recipient_email: EmailStr
    status: str = Field(default="active", min_length=4, max_length=20)
    config_json: dict[str, Any] | None = None
    next_run_at: datetime | None = None

    @field_validator("name", "report_type", "frequency", "status", mode="before")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        cleaned = value.strip().lower() if isinstance(value, str) else ""
        if not cleaned:
            raise ValueError("value is required")
        return cleaned


class ReportScheduleOut(BaseModel):
    id: str
    name: str
    report_type: str
    frequency: str
    recipient_email: str
    status: str
    config_json: dict[str, Any] | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReportScheduleListOut(BaseModel):
    items: list[ReportScheduleOut]
