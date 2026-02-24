from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import PaginationMeta


AutomationRuleStatus = Literal["active", "inactive"]
AutomationTriggerSource = Literal["outbox_event"]
AutomationActionType = Literal["send_message", "tag_customer", "create_task", "apply_discount"]
AutomationRunStatus = Literal["success", "failed", "skipped", "blocked", "dry_run"]
AutomationStepStatus = Literal["success", "failed", "skipped", "rolled_back", "dry_run"]
AutomationConditionOperator = Literal[
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "in",
    "exists",
    "not_exists",
]
AutomationTemplateKey = Literal["abandoned_cart", "overdue_invoice", "low_stock"]


class AutomationConditionIn(BaseModel):
    field: str = Field(min_length=1, max_length=120)
    operator: AutomationConditionOperator = "eq"
    value: Any | None = None
    case_sensitive: bool = False


class AutomationActionIn(BaseModel):
    type: AutomationActionType
    config_json: dict[str, Any] = Field(default_factory=dict)


class AutomationRuleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    status: AutomationRuleStatus = "active"
    trigger_source: AutomationTriggerSource = "outbox_event"
    trigger_event_type: str = Field(default="*", min_length=1, max_length=120)
    conditions: list[AutomationConditionIn] = Field(default_factory=list)
    actions: list[AutomationActionIn] = Field(default_factory=list)
    template_key: str | None = Field(default=None, max_length=60)
    run_limit_per_hour: int = Field(default=120, ge=1, le=5000)
    reentry_cooldown_seconds: int = Field(default=300, ge=0, le=86400)
    rollback_on_failure: bool = True

    @model_validator(mode="after")
    def validate_actions_not_empty(self) -> "AutomationRuleCreateIn":
        if not self.actions:
            raise ValueError("At least one action is required")
        return self


class AutomationRuleUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    status: AutomationRuleStatus | None = None
    trigger_event_type: str | None = Field(default=None, min_length=1, max_length=120)
    conditions: list[AutomationConditionIn] | None = None
    actions: list[AutomationActionIn] | None = None
    run_limit_per_hour: int | None = Field(default=None, ge=1, le=5000)
    reentry_cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    rollback_on_failure: bool | None = None

    @model_validator(mode="after")
    def validate_has_updates(self) -> "AutomationRuleUpdateIn":
        if (
            self.name is None
            and self.description is None
            and self.status is None
            and self.trigger_event_type is None
            and self.conditions is None
            and self.actions is None
            and self.run_limit_per_hour is None
            and self.reentry_cooldown_seconds is None
            and self.rollback_on_failure is None
        ):
            raise ValueError("At least one field must be provided")
        if self.actions is not None and not self.actions:
            raise ValueError("At least one action is required")
        return self


class AutomationConditionOut(BaseModel):
    field: str
    operator: AutomationConditionOperator
    value: Any | None = None
    case_sensitive: bool = False


class AutomationActionOut(BaseModel):
    type: AutomationActionType
    config_json: dict[str, Any]


class AutomationRuleOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: AutomationRuleStatus
    trigger_source: AutomationTriggerSource
    trigger_event_type: str
    conditions: list[AutomationConditionOut]
    actions: list[AutomationActionOut]
    template_key: str | None = None
    version: int
    run_limit_per_hour: int
    reentry_cooldown_seconds: int
    rollback_on_failure: bool
    created_by_user_id: str
    updated_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AutomationRuleListOut(BaseModel):
    items: list[AutomationRuleOut]
    pagination: PaginationMeta
    status: AutomationRuleStatus | None = None
    trigger_event_type: str | None = None


class AutomationRuleTestIn(BaseModel):
    event_type: str | None = Field(default=None, min_length=1, max_length=120)
    target_app_key: str = Field(default="automation", min_length=1, max_length=60)
    payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "invoice.overdue",
                "target_app_key": "automation",
                "payload_json": {"customer_id": "cus-123", "phone": "+2348000000000"},
            }
        }
    )


class AutomationRuleStepOut(BaseModel):
    id: str | None = None
    step_index: int
    action_type: AutomationActionType
    status: AutomationStepStatus
    input_json: dict[str, Any] | None = None
    output_json: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime | None = None


class AutomationRuleRunOut(BaseModel):
    id: str
    rule_id: str
    trigger_event_id: str | None = None
    trigger_event_type: str
    status: AutomationRunStatus
    blocked_reason: str | None = None
    error_message: str | None = None
    steps_total: int
    steps_succeeded: int
    steps_failed: int
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    steps: list[AutomationRuleStepOut] = []


class AutomationRuleRunListOut(BaseModel):
    items: list[AutomationRuleRunOut]
    pagination: PaginationMeta
    rule_id: str | None = None
    status: AutomationRunStatus | None = None


class AutomationOutboxRunOut(BaseModel):
    processed_events: int
    matched_rules: int
    triggered_runs: int
    successful_runs: int
    failed_runs: int
    blocked_runs: int
    skipped_runs: int


class AutomationTemplateOut(BaseModel):
    template_key: AutomationTemplateKey
    name: str
    description: str
    trigger_event_type: str
    default_conditions: list[AutomationConditionOut]
    default_actions: list[AutomationActionOut]


class AutomationTemplateCatalogOut(BaseModel):
    items: list[AutomationTemplateOut]


class AutomationTemplateInstallIn(BaseModel):
    template_key: AutomationTemplateKey
    activate: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_key": "abandoned_cart",
                "activate": True,
            }
        }
    )


class AutomationTemplateInstallOut(BaseModel):
    template: AutomationTemplateOut
    rule: AutomationRuleOut
