from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import PaginationMeta


CampaignChannel = Literal["whatsapp", "sms", "email"]
CampaignTemplateStatus = Literal["draft", "approved", "archived"]
CampaignStatus = Literal["draft", "queued", "sending", "completed", "failed", "cancelled"]
CampaignRecipientStatus = Literal["queued", "sent", "delivered", "opened", "replied", "failed", "suppressed", "skipped"]
ConsentStatus = Literal["subscribed", "unsubscribed"]
RetentionTriggerStatus = Literal["active", "inactive"]


class SegmentFiltersIn(BaseModel):
    q: str | None = None
    tag_ids_any: list[str] = Field(default_factory=list)
    min_total_spent: float | None = Field(default=None, ge=0)
    min_order_count: int | None = Field(default=None, ge=0)
    channels_any: list[str] = Field(default_factory=list)
    has_email: bool | None = None
    has_phone: bool | None = None
    last_order_before_days: int | None = Field(default=None, ge=0)
    last_order_within_days: int | None = Field(default=None, ge=0)


class CustomerSegmentCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    filters: SegmentFiltersIn = Field(default_factory=SegmentFiltersIn)


class CustomerSegmentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    filters: SegmentFiltersIn | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_has_field(self) -> "CustomerSegmentUpdateIn":
        if (
            self.name is None
            and self.description is None
            and self.filters is None
            and self.is_active is None
        ):
            raise ValueError("At least one field must be provided")
        return self


class CustomerSegmentOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    filters: SegmentFiltersIn
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerSegmentListOut(BaseModel):
    items: list[CustomerSegmentOut]
    pagination: PaginationMeta


class SegmentPreviewOut(BaseModel):
    segment_id: str
    total_customers: int
    customer_ids: list[str]


class CampaignTemplateCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    channel: CampaignChannel = "whatsapp"
    content: str = Field(min_length=1, max_length=2000)
    status: CampaignTemplateStatus = "draft"


class CampaignTemplateUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    channel: CampaignChannel | None = None
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    status: CampaignTemplateStatus | None = None

    @model_validator(mode="after")
    def validate_has_field(self) -> "CampaignTemplateUpdateIn":
        if self.name is None and self.channel is None and self.content is None and self.status is None:
            raise ValueError("At least one field must be provided")
        return self


class CampaignTemplateOut(BaseModel):
    id: str
    name: str
    channel: CampaignChannel
    content: str
    status: CampaignTemplateStatus
    created_by_user_id: str
    approved_by_user_id: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CampaignTemplateListOut(BaseModel):
    items: list[CampaignTemplateOut]
    pagination: PaginationMeta


class CustomerConsentUpsertIn(BaseModel):
    customer_id: str
    channel: CampaignChannel = "whatsapp"
    status: ConsentStatus
    source: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=255)


class CustomerConsentOut(BaseModel):
    id: str
    customer_id: str
    channel: CampaignChannel
    status: ConsentStatus
    source: str | None = None
    note: str | None = None
    opted_at: datetime
    updated_at: datetime


class CustomerConsentListOut(BaseModel):
    items: list[CustomerConsentOut]
    pagination: PaginationMeta
    channel: CampaignChannel | None = None
    status: ConsentStatus | None = None


class CampaignCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    segment_id: str | None = None
    template_id: str | None = None
    explicit_customer_ids: list[str] = Field(default_factory=list)
    channel: CampaignChannel = "whatsapp"
    provider: str = Field(default="whatsapp_stub", min_length=2, max_length=60)
    content_override: str | None = Field(default=None, max_length=2000)
    scheduled_at: datetime | None = None
    send_now: bool = False


class CampaignOut(BaseModel):
    id: str
    name: str
    segment_id: str | None = None
    template_id: str | None = None
    channel: CampaignChannel
    provider: str
    message_content: str
    status: CampaignStatus
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_recipients: int
    sent_count: int
    delivered_count: int
    opened_count: int
    replied_count: int
    failed_count: int
    suppressed_count: int
    skipped_count: int
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class CampaignListOut(BaseModel):
    items: list[CampaignOut]
    pagination: PaginationMeta
    status: CampaignStatus | None = None


class CampaignDispatchIn(BaseModel):
    provider: str | None = Field(default=None, min_length=2, max_length=60)


class CampaignDispatchOut(BaseModel):
    campaign_id: str
    campaign_status: CampaignStatus
    processed: int
    sent: int
    failed: int
    suppressed: int
    skipped: int


class CampaignRecipientOut(BaseModel):
    id: str
    campaign_id: str
    customer_id: str
    recipient: str
    status: CampaignRecipientStatus
    outbound_message_id: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    opened_at: datetime | None = None
    replied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CampaignRecipientListOut(BaseModel):
    items: list[CampaignRecipientOut]
    pagination: PaginationMeta
    status: CampaignRecipientStatus | None = None


class CampaignMetricsOut(BaseModel):
    campaigns_total: int
    recipients_total: int
    queued_count: int
    sent_count: int
    delivered_count: int
    opened_count: int
    replied_count: int
    failed_count: int
    suppressed_count: int
    skipped_count: int
    response_rate: float


class RetentionTriggerCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    trigger_type: str = Field(default="repeat_purchase_nudge", min_length=2, max_length=40)
    status: RetentionTriggerStatus = "active"
    segment_id: str | None = None
    template_id: str | None = None
    channel: CampaignChannel = "whatsapp"
    provider: str = Field(default="whatsapp_stub", min_length=2, max_length=60)
    config_json: dict[str, Any] = Field(default_factory=dict)


class RetentionTriggerOut(BaseModel):
    id: str
    name: str
    trigger_type: str
    status: RetentionTriggerStatus
    segment_id: str | None = None
    template_id: str | None = None
    channel: CampaignChannel
    provider: str
    config_json: dict[str, Any] | None = None
    created_by_user_id: str
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RetentionTriggerListOut(BaseModel):
    items: list[RetentionTriggerOut]
    pagination: PaginationMeta


class RetentionTriggerRunOut(BaseModel):
    id: str
    retention_trigger_id: str
    campaign_id: str | None = None
    status: str
    processed_count: int
    queued_count: int
    skipped_count: int
    error_count: int
    created_at: datetime


class RetentionTriggerRunRequestIn(BaseModel):
    auto_dispatch: bool = True

    model_config = ConfigDict(
        json_schema_extra={"example": {"auto_dispatch": True}}
    )
