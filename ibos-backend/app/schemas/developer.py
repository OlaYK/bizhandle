from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta

PublicApiKeyStatus = Literal["active", "revoked"]
WebhookSubscriptionStatus = Literal["active", "paused"]
WebhookDeliveryStatus = Literal["pending", "delivered", "failed", "dead_letter"]
MarketplaceListingStatus = Literal[
    "draft",
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "published",
]


class PublicApiScopeOut(BaseModel):
    scope: str
    description: str


class PublicApiScopeCatalogOut(BaseModel):
    items: list[PublicApiScopeOut]


class PublicApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class PublicApiKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    status: PublicApiKeyStatus
    version: int
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PublicApiKeyCreateOut(PublicApiKeyOut):
    api_key: str


class PublicApiKeyRotateOut(PublicApiKeyOut):
    api_key: str


class PublicApiKeyListOut(BaseModel):
    items: list[PublicApiKeyOut]


class WebhookSubscriptionCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    endpoint_url: str = Field(min_length=10, max_length=500)
    description: str | None = Field(default=None, max_length=255)
    events: list[str] = Field(default_factory=lambda: ["*"])
    max_attempts: int = Field(default=5, ge=1, le=20)
    retry_seconds: int = Field(default=300, ge=0, le=86400)


class WebhookSubscriptionUpdateIn(BaseModel):
    endpoint_url: str | None = Field(default=None, min_length=10, max_length=500)
    description: str | None = Field(default=None, max_length=255)
    events: list[str] | None = None
    status: WebhookSubscriptionStatus | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=20)
    retry_seconds: int | None = Field(default=None, ge=0, le=86400)


class WebhookSubscriptionOut(BaseModel):
    id: str
    name: str
    endpoint_url: str
    description: str | None = None
    events: list[str]
    status: WebhookSubscriptionStatus
    max_attempts: int
    retry_seconds: int
    secret_hint: str
    last_delivery_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebhookSubscriptionCreateOut(WebhookSubscriptionOut):
    signing_secret: str


class WebhookSubscriptionRotateSecretOut(BaseModel):
    subscription_id: str
    signing_secret: str
    rotated_at: datetime


class WebhookSubscriptionListOut(BaseModel):
    items: list[WebhookSubscriptionOut]


class WebhookDeliveryOut(BaseModel):
    id: str
    subscription_id: str
    outbox_event_id: str
    event_type: str
    status: WebhookDeliveryStatus
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    last_error: str | None = None
    last_response_code: int | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryListOut(BaseModel):
    items: list[WebhookDeliveryOut]
    pagination: PaginationMeta
    subscription_id: str | None = None
    status: WebhookDeliveryStatus | None = None


class WebhookDispatchOut(BaseModel):
    enqueued: int
    processed: int
    delivered: int
    failed: int
    dead_lettered: int


class PublicApiBusinessOut(BaseModel):
    business_id: str
    business_name: str
    base_currency: str


class PublicApiProductOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    is_published: bool
    created_at: datetime


class PublicApiProductListOut(BaseModel):
    items: list[PublicApiProductOut]
    pagination: PaginationMeta
    q: str | None = None
    category: str | None = None
    is_published: bool | None = None


class PublicApiOrderOut(BaseModel):
    id: str
    customer_id: str | None = None
    payment_method: str
    channel: str
    status: str
    total_amount: float
    created_at: datetime
    updated_at: datetime


class PublicApiOrderListOut(BaseModel):
    items: list[PublicApiOrderOut]
    pagination: PaginationMeta
    status: str | None = None


class PublicApiCustomerOut(BaseModel):
    id: str
    name: str
    email: str | None = None
    phone: str | None = None
    created_at: datetime
    updated_at: datetime


class PublicApiCustomerListOut(BaseModel):
    items: list[PublicApiCustomerOut]
    pagination: PaginationMeta
    q: str | None = None


class MarketplaceListingCreateIn(BaseModel):
    app_key: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=500)
    category: str = Field(default="operations", min_length=2, max_length=60)
    requested_scopes: list[str] = Field(default_factory=list)


class MarketplaceListingReviewIn(BaseModel):
    decision: Literal["under_review", "approved", "rejected"]
    review_notes: str | None = Field(default=None, max_length=500)


class MarketplaceListingPublishIn(BaseModel):
    publish: bool = True


class MarketplaceListingOut(BaseModel):
    id: str
    app_key: str
    display_name: str
    description: str
    category: str
    requested_scopes: list[str]
    status: MarketplaceListingStatus
    review_notes: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MarketplaceListingListOut(BaseModel):
    items: list[MarketplaceListingOut]
    pagination: PaginationMeta
    status: MarketplaceListingStatus | None = None


class DeveloperPortalDocOut(BaseModel):
    section: str
    title: str
    summary: str
    relative_path: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "section": "sdk",
                "title": "Node SDK Quickstart",
                "summary": "Create API key, call products endpoint, and verify signature.",
                "relative_path": "docs/sdk/node-quickstart.md",
            }
        }
    )


class DeveloperPortalDocsOut(BaseModel):
    items: list[DeveloperPortalDocOut]
    generated_at: datetime


class DeveloperWebhookReplayIn(BaseModel):
    outbox_event_id: str
    payload_json: dict[str, Any] | None = None
