from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CustomerPiiOrderOut(BaseModel):
    id: str
    reference: str | None = None
    status: str
    channel: str
    total_amount: float
    created_at: datetime


class CustomerPiiInvoiceOut(BaseModel):
    id: str
    reference: str | None = None
    status: str
    currency: str
    total_amount: float
    amount_paid: float
    issue_date: datetime | None = None
    created_at: datetime


class CustomerPiiDocumentOut(BaseModel):
    id: str
    document_type: str
    title: str
    status: str
    file_url: str | None = None
    signed_at: datetime | None = None
    created_at: datetime


class CustomerPiiExportOut(BaseModel):
    customer_id: str
    exported_at: datetime
    customer: dict[str, Any]
    orders: list[CustomerPiiOrderOut]
    invoices: list[CustomerPiiInvoiceOut]
    documents: list[CustomerPiiDocumentOut] = Field(default_factory=list)


class CustomerPiiDeleteOut(BaseModel):
    customer_id: str
    anonymized: bool
    deleted_fields: list[str]
    processed_at: datetime


class AuditArchiveOut(BaseModel):
    archive_id: str
    cutoff_date: datetime
    records_count: int
    archived_at: datetime


class RolePermissionOut(BaseModel):
    role: str
    permissions: list[str]


class PermissionMatrixOut(BaseModel):
    items: list[RolePermissionOut]


class CustomerDocumentCreateIn(BaseModel):
    customer_id: str
    order_id: str | None = None
    invoice_id: str | None = None
    document_type: str
    title: str
    file_url: str | None = None
    consent_text: str | None = None
    recipient_name: str | None = None
    recipient_email: str | None = None
    recipient_phone: str | None = None
    expires_in_days: int = Field(default=30, ge=1, le=365)
    metadata_json: dict[str, Any] | None = None

    @field_validator("document_type", "title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value is required")
        return cleaned

    @field_validator(
        "file_url",
        "consent_text",
        "recipient_name",
        "recipient_email",
        "recipient_phone",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CustomerDocumentSignIn(BaseModel):
    accepted: bool
    signer_name: str | None = None
    note: str | None = None

    @field_validator("signer_name", "note")
    @classmethod
    def normalize_sign_inputs(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CustomerDocumentOut(BaseModel):
    id: str
    customer_id: str
    customer_name: str | None = None
    order_id: str | None = None
    order_reference: str | None = None
    invoice_id: str | None = None
    invoice_reference: str | None = None
    document_type: str
    title: str
    status: str
    file_url: str | None = None
    consent_text: str | None = None
    recipient_name: str | None = None
    recipient_email: str | None = None
    recipient_phone: str | None = None
    share_url: str | None = None
    sign_token_expires_at: datetime | None = None
    signed_by_name: str | None = None
    signed_at: datetime | None = None
    signer_ip: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CustomerDocumentListOut(BaseModel):
    items: list[CustomerDocumentOut]


class CustomerDocumentPublicOut(BaseModel):
    title: str
    document_type: str
    status: str
    file_url: str | None = None
    consent_text: str | None = None
    recipient_name: str | None = None
    sign_token_expires_at: datetime | None = None
    signed_by_name: str | None = None
    signed_at: datetime | None = None
