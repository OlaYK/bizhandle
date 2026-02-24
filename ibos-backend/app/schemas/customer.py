from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.schemas.common import PaginationMeta


class CustomerTagCreateIn(BaseModel):
    name: str
    color: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "VIP", "color": "#16a34a"}}
    )


class CustomerTagOut(BaseModel):
    id: str
    name: str
    color: str | None = None
    created_at: datetime


class CustomerTagListOut(BaseModel):
    items: list[CustomerTagOut]


class CustomerCreateIn(BaseModel):
    name: str
    phone: str | None = None
    email: EmailStr | None = None
    note: str | None = None
    tag_ids: list[str] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("phone", "note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> EmailStr | None:
        if value is None:
            return None
        return str(value).strip().lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Aisha Bello",
                "phone": "+2348011112222",
                "email": "aisha@example.com",
                "note": "Prefers WhatsApp updates",
                "tag_ids": ["tag-id"],
            }
        }
    )


class CustomerUpdateIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    note: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name cannot be empty")
        return cleaned

    @field_validator("phone", "note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> EmailStr | None:
        if value is None:
            return None
        return str(value).strip().lower()

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "CustomerUpdateIn":
        if self.name is None and self.phone is None and self.email is None and self.note is None:
            raise ValueError("At least one field must be provided")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Aisha Bello Updated",
                "phone": "+2348019990000",
                "email": "aisha.updated@example.com",
                "note": "Top repeat buyer",
            }
        }
    )


class CustomerCreateOut(BaseModel):
    id: str


class CustomerOut(BaseModel):
    id: str
    name: str
    phone: str | None = None
    email: EmailStr | None = None
    note: str | None = None
    tags: list[CustomerTagOut] = []
    created_at: datetime
    updated_at: datetime


class CustomerListOut(BaseModel):
    items: list[CustomerOut]
    pagination: PaginationMeta
    q: str | None = None
    tag_id: str | None = None


class CustomerCsvImportIn(BaseModel):
    csv_content: str
    has_header: bool = True
    delimiter: str = ","
    default_tag_ids: list[str] = []

    @field_validator("csv_content")
    @classmethod
    def validate_csv_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("csv_content is required")
        return value

    @field_validator("delimiter")
    @classmethod
    def validate_delimiter(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) != 1:
            raise ValueError("delimiter must be a single character")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "csv_content": "name,email,phone,note\nAisha,aisha@example.com,+2348011112222,VIP customer",
                "has_header": True,
                "delimiter": ",",
                "default_tag_ids": ["tag-id"],
            }
        }
    )


class CustomerCsvImportRejectedOut(BaseModel):
    row_number: int
    reason: str
    row_data: dict[str, str]


class CustomerCsvImportOut(BaseModel):
    total_rows: int
    imported_count: int
    rejected_count: int
    imported_ids: list[str]
    rejected_rows: list[CustomerCsvImportRejectedOut]
