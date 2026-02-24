from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIAskIn(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question cannot be empty")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What is my current profit and one action to improve it this week?"
            }
        }
    )


class AITokenUsageOut(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class AIResponseOut(BaseModel):
    id: str
    insight_type: str
    response: str
    provider: str
    model: str
    token_usage: Optional[AITokenUsageOut] = None
    estimated_cost_usd: Optional[float] = None


class AIFeatureSnapshotOut(BaseModel):
    id: str
    window_start_date: date
    window_end_date: date
    orders_count: int
    paid_orders_count: int
    gross_revenue: float
    refunds_count: int
    refunds_amount: float
    net_revenue: float
    expenses_total: float
    refund_rate: float
    stockout_events_count: int
    campaigns_sent_count: int
    campaigns_failed_count: int
    repeat_customers_count: int
    created_at: datetime


class AIInsightV2Out(BaseModel):
    id: str
    feature_snapshot_id: str | None = None
    insight_type: str
    severity: str
    title: str
    summary: str
    confidence_score: float = Field(ge=0, le=1)
    status: str
    context_json: dict | None = None
    created_at: datetime


class AIInsightV2ListOut(BaseModel):
    items: list[AIInsightV2Out]
    status: str | None = None
    insight_type: str | None = None


class AIPrescriptiveActionOut(BaseModel):
    id: str
    insight_id: str
    action_type: str
    title: str
    description: str
    payload_json: dict | None = None
    status: str
    decision_note: str | None = None
    decided_by_user_id: str | None = None
    decided_at: datetime | None = None
    executed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AIPrescriptiveActionListOut(BaseModel):
    items: list[AIPrescriptiveActionOut]
    status: str | None = None


class AIPrescriptiveDecisionIn(BaseModel):
    decision: str
    note: str | None = Field(default=None, max_length=255)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError("decision must be either 'approve' or 'reject'")
        return normalized


class AIInsightsGenerateOut(BaseModel):
    snapshot: AIFeatureSnapshotOut
    insights: list[AIInsightV2Out]
    actions_created: int


class AIAnalyticsAssistantQueryIn(BaseModel):
    question: str
    window_days: int = Field(default=30, ge=7, le=120)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question cannot be empty")
        return cleaned


class AIAnalyticsAssistantMetricOut(BaseModel):
    key: str
    value: float | str
    source: str


class AIAnalyticsAssistantOut(BaseModel):
    answer: str
    grounded_metrics: list[AIAnalyticsAssistantMetricOut]
    trace_id: str


class AIRiskAlertConfigIn(BaseModel):
    enabled: bool = True
    refund_rate_threshold: float = Field(default=0.1, ge=0, le=1)
    stockout_threshold: int = Field(default=3, ge=0, le=5000)
    cashflow_margin_threshold: float = Field(default=0.15, ge=-1, le=1)
    channels: list[str] = Field(default_factory=lambda: ["in_app"])


class AIRiskAlertConfigOut(BaseModel):
    id: str
    enabled: bool
    refund_rate_threshold: float
    stockout_threshold: int
    cashflow_margin_threshold: float
    channels: list[str]
    updated_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AIRiskAlertEventOut(BaseModel):
    id: str
    alert_type: str
    severity: str
    status: str
    message: str
    triggered_value: float
    threshold_value: float
    channels: list[str]
    context_json: dict | None = None
    created_at: datetime


class AIRiskAlertEventListOut(BaseModel):
    items: list[AIRiskAlertEventOut]
    status: str | None = None
    alert_type: str | None = None


class AIRiskAlertRunOut(BaseModel):
    triggered_count: int
    snapshot_id: str
    events: list[AIRiskAlertEventOut]


class AIGovernanceTraceOut(BaseModel):
    id: str
    trace_type: str
    actor_user_id: str | None = None
    feature_snapshot_id: str | None = None
    created_at: datetime


class AIGovernanceTraceDetailOut(AIGovernanceTraceOut):
    prompt: str
    context_json: dict | None = None
    output_json: dict | None = None


class AIGovernanceTraceListOut(BaseModel):
    items: list[AIGovernanceTraceOut]
    trace_type: str | None = None
