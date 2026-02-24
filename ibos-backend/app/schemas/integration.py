from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class IntegrationSecretUpsertIn(BaseModel):
    provider: str = Field(min_length=2, max_length=60)
    key_name: str = Field(min_length=2, max_length=80)
    secret_value: str = Field(min_length=2, max_length=1000)


class IntegrationSecretOut(BaseModel):
    id: str
    provider: str
    key_name: str
    version: int
    status: str
    rotated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationSecretListOut(BaseModel):
    items: list[IntegrationSecretOut]


class AppInstallationIn(BaseModel):
    app_key: str = Field(min_length=2, max_length=60)
    display_name: str = Field(min_length=2, max_length=120)
    permissions: list[str] = Field(default_factory=list)
    config_json: dict[str, Any] | None = None


class AppInstallationOut(BaseModel):
    id: str
    app_key: str
    display_name: str
    status: str
    permissions: list[str]
    config_json: dict[str, Any] | None = None
    installed_at: datetime
    disconnected_at: datetime | None = None
    updated_at: datetime


class AppInstallationListOut(BaseModel):
    items: list[AppInstallationOut]


class IntegrationOutboxEventOut(BaseModel):
    id: str
    event_type: str
    target_app_key: str
    status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationOutboxEventListOut(BaseModel):
    items: list[IntegrationOutboxEventOut]
    pagination: PaginationMeta
    status: str | None = None
    target_app_key: str | None = None


class IntegrationDispatchOut(BaseModel):
    processed: int
    delivered: int
    failed: int
    dead_lettered: int


class IntegrationMessageSendIn(BaseModel):
    provider: str = Field(default="whatsapp_stub", min_length=2, max_length=60)
    recipient: str = Field(min_length=3, max_length=120)
    content: str = Field(min_length=1, max_length=1000)


class IntegrationMessageOut(BaseModel):
    id: str
    provider: str
    recipient: str
    content: str
    status: str
    external_message_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationMessageListOut(BaseModel):
    items: list[IntegrationMessageOut]
    pagination: PaginationMeta


class IntegrationEventEmitIn(BaseModel):
    event_type: str = Field(min_length=2, max_length=120)
    target_app_key: str = Field(min_length=2, max_length=60)
    payload_json: dict[str, Any] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "storefront.page_view",
                "target_app_key": "meta_pixel",
                "payload_json": {"slug": "ankara-house"},
            }
        }
    )


class IntegrationEmitOut(BaseModel):
    event_id: str
