from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CustomerPiiOrderOut(BaseModel):
    id: str
    status: str
    channel: str
    total_amount: float
    created_at: datetime


class CustomerPiiInvoiceOut(BaseModel):
    id: str
    status: str
    currency: str
    total_amount: float
    amount_paid: float
    issue_date: datetime | None = None
    created_at: datetime


class CustomerPiiExportOut(BaseModel):
    customer_id: str
    exported_at: datetime
    customer: dict[str, Any]
    orders: list[CustomerPiiOrderOut]
    invoices: list[CustomerPiiInvoiceOut]


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
