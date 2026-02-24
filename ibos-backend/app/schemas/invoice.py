from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import PaginationMeta
from app.schemas.sales import PaymentMethod

InvoiceStatus = str
ALLOWED_INVOICE_STATUSES = {"draft", "sent", "partially_paid", "paid", "overdue", "cancelled"}
ReminderChannel = str
ALLOWED_REMINDER_CHANNELS = {"email", "sms", "whatsapp"}
ALLOWED_TEMPLATE_STATUSES = {"active", "archived"}


class InvoiceInstallmentCreateIn(BaseModel):
    due_date: date
    amount: Decimal = Field(gt=0)
    note: str | None = None

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class InvoiceReminderPolicyIn(BaseModel):
    enabled: bool = False
    first_delay_days: int = Field(default=3, ge=0, le=180)
    cadence_days: int = Field(default=3, ge=1, le=180)
    max_reminders: int = Field(default=3, ge=1, le=50)
    escalation_after_days: int = Field(default=14, ge=1, le=365)
    channels: list[ReminderChannel] = Field(default_factory=lambda: ["email"])

    @field_validator("channels")
    @classmethod
    def _validate_channels(cls, value: list[str]) -> list[str]:
        normalized = [(item or "").strip().lower() for item in value if (item or "").strip()]
        if not normalized:
            normalized = ["email"]
        invalid = [item for item in normalized if item not in ALLOWED_REMINDER_CHANNELS]
        if invalid:
            allowed = ", ".join(sorted(ALLOWED_REMINDER_CHANNELS))
            raise ValueError(f"Invalid reminder channels: {', '.join(invalid)}. Allowed: {allowed}")
        return list(dict.fromkeys(normalized))


class InvoiceCreate(BaseModel):
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    currency: str = "USD"
    fx_rate_to_base: Decimal | None = Field(default=None, gt=0)
    total_amount: Decimal | None = Field(default=None, gt=0)
    issue_date: date | None = None
    due_date: date | None = None
    note: Optional[str] = None
    template_id: str | None = None
    reminder_policy: InvoiceReminderPolicyIn | None = None
    installments: list[InvoiceInstallmentCreateIn] = Field(default_factory=list)
    send_now: bool = False

    @field_validator("customer_id", "order_id", "note", "template_id")
    @classmethod
    def _normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("currency is required")
        if len(cleaned) != 3:
            raise ValueError("currency must be a 3-letter code")
        return cleaned

    @model_validator(mode="after")
    def _validate_dates_and_installments(self) -> "InvoiceCreate":
        if self.issue_date and self.due_date and self.due_date < self.issue_date:
            raise ValueError("due_date cannot be before issue_date")
        if self.installments:
            issue = self.issue_date or date.today()
            if any(item.due_date < issue for item in self.installments):
                raise ValueError("installment due_date cannot be before issue_date")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "customer-id",
                "order_id": "order-id",
                "currency": "EUR",
                "fx_rate_to_base": 1.1,
                "total_amount": 450.0,
                "issue_date": "2026-02-21",
                "due_date": "2026-02-28",
                "template_id": "template-id",
                "reminder_policy": {
                    "enabled": True,
                    "first_delay_days": 2,
                    "cadence_days": 3,
                    "max_reminders": 4,
                    "escalation_after_days": 10,
                    "channels": ["email", "whatsapp"],
                },
                "installments": [
                    {"due_date": "2026-02-24", "amount": 150.0},
                    {"due_date": "2026-02-27", "amount": 300.0},
                ],
                "note": "Pay within 7 days",
                "send_now": True,
            }
        }
    )


class InvoiceMarkPaidIn(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    payment_method: PaymentMethod | None = None
    payment_reference: str | None = None
    idempotency_key: str | None = None
    note: str | None = None

    @field_validator("payment_reference", "idempotency_key", "note")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "amount": 200.0,
                "payment_method": "transfer",
                "payment_reference": "bank-ref-001",
                "idempotency_key": "pay-evt-001",
                "note": "Partial transfer",
            }
        }
    )


class InvoicePaymentCreateIn(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method: PaymentMethod | None = None
    payment_reference: str | None = None
    idempotency_key: str | None = None
    paid_at: datetime | None = None
    note: str | None = None

    @field_validator("payment_reference", "idempotency_key", "note")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class InvoiceInstallmentUpsertIn(BaseModel):
    items: list[InvoiceInstallmentCreateIn]

    @model_validator(mode="after")
    def _validate_items(self) -> "InvoiceInstallmentUpsertIn":
        if not self.items:
            raise ValueError("At least one installment is required")
        return self


class InvoiceReminderIn(BaseModel):
    channel: ReminderChannel = "email"
    note: str | None = None

    @field_validator("channel")
    @classmethod
    def _normalize_channel(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_REMINDER_CHANNELS:
            allowed = ", ".join(sorted(ALLOWED_REMINDER_CHANNELS))
            raise ValueError(f"Invalid reminder channel. Allowed: {allowed}")
        return normalized

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel": "whatsapp",
                "note": "Customer requested WhatsApp reminder",
            }
        }
    )


class InvoiceTemplateUpsertIn(BaseModel):
    template_id: str | None = None
    name: str = Field(min_length=2, max_length=120)
    status: str = "active"
    is_default: bool = False
    brand_name: str | None = Field(default=None, max_length=120)
    logo_url: str | None = Field(default=None, max_length=500)
    primary_color: str | None = Field(default=None, max_length=20)
    footer_text: str | None = Field(default=None, max_length=255)
    config_json: dict[str, Any] | None = None

    @field_validator("template_id", "brand_name", "logo_url", "primary_color", "footer_text")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("status")
    @classmethod
    def _normalize_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_TEMPLATE_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_TEMPLATE_STATUSES))
            raise ValueError(f"Invalid template status. Allowed: {allowed}")
        return normalized


class InvoiceTemplateOut(BaseModel):
    id: str
    name: str
    status: str
    is_default: bool
    brand_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    footer_text: str | None = None
    config_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class InvoiceTemplateListOut(BaseModel):
    items: list[InvoiceTemplateOut]


class InvoiceCreateOut(BaseModel):
    id: str
    status: InvoiceStatus
    total_amount: float
    total_amount_base: float
    currency: str
    base_currency: str


class InvoiceInstallmentOut(BaseModel):
    id: str
    due_date: date
    amount: float
    paid_amount: float
    remaining_amount: float
    status: str
    note: str | None = None


class InvoiceInstallmentListOut(BaseModel):
    items: list[InvoiceInstallmentOut]
    total_scheduled: float
    total_paid: float
    total_remaining: float


class InvoicePaymentOut(BaseModel):
    id: str
    invoice_id: str
    amount: float
    amount_base: float
    currency: str
    fx_rate_to_base: float
    payment_method: PaymentMethod | None = None
    payment_reference: str | None = None
    idempotency_key: str | None = None
    note: str | None = None
    paid_at: datetime
    created_at: datetime


class InvoicePaymentListOut(BaseModel):
    items: list[InvoicePaymentOut]
    pagination: PaginationMeta


class InvoiceReminderPolicyOut(BaseModel):
    enabled: bool
    first_delay_days: int
    cadence_days: int
    max_reminders: int
    escalation_after_days: int
    channels: list[str]
    reminder_count: int
    escalation_level: int
    next_reminder_at: datetime | None = None


class InvoiceReminderRunOut(BaseModel):
    processed_count: int
    reminders_created: int
    escalated_count: int
    next_due_count: int


class InvoiceOut(BaseModel):
    id: str
    customer_id: str | None = None
    order_id: str | None = None
    status: InvoiceStatus
    currency: str
    base_currency: str
    fx_rate_to_base: float
    total_amount: float
    total_amount_base: float
    amount_paid: float
    amount_paid_base: float
    outstanding_amount: float
    outstanding_amount_base: float
    template_id: str | None = None
    payment_reference: str | None = None
    payment_method: PaymentMethod | None = None
    issue_date: date
    due_date: date | None = None
    last_sent_at: datetime | None = None
    paid_at: datetime | None = None
    reminder_count: int
    escalation_level: int
    next_reminder_at: datetime | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class InvoiceListOut(BaseModel):
    pagination: PaginationMeta
    start_date: date | None = None
    end_date: date | None = None
    status: InvoiceStatus | None = None
    customer_id: str | None = None
    order_id: str | None = None
    items: list[InvoiceOut]


class InvoiceFxQuoteOut(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    as_of: datetime


class InvoiceAgingBucketOut(BaseModel):
    bucket: str
    amount: float
    count: int


class InvoiceAgingCustomerOut(BaseModel):
    customer_id: str | None = None
    amount: float
    count: int


class InvoiceAgingDashboardOut(BaseModel):
    as_of_date: date
    base_currency: str
    total_outstanding: float
    overdue_count: int
    partially_paid_count: int
    buckets: list[InvoiceAgingBucketOut]
    by_currency: dict[str, float]
    top_customers: list[InvoiceAgingCustomerOut]


class InvoiceStatementItemOut(BaseModel):
    customer_id: str | None = None
    invoices_count: int
    total_invoiced: float
    total_paid: float
    total_outstanding: float
    by_currency: dict[str, float]


class InvoiceStatementListOut(BaseModel):
    items: list[InvoiceStatementItemOut]
    start_date: date
    end_date: date


class InvoiceStatementExportOut(BaseModel):
    filename: str
    content_type: str
    row_count: int
    csv_content: str
