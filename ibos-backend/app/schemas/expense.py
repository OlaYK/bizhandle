from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PaginationMeta


class ExpenseCreate(BaseModel):
    category: str
    amount: Decimal = Field(gt=0)
    note: Optional[str] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("category is required")
        return cleaned

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "logistics",
                "amount": 25.0,
                "note": "Dispatch rider payment",
            }
        }
    )


class ExpenseCreateOut(BaseModel):
    id: str


class ExpenseOut(BaseModel):
    id: str
    category: str
    amount: float
    note: Optional[str] = None
    created_at: datetime


class ExpenseListOut(BaseModel):
    pagination: PaginationMeta
    start_date: date | None = None
    end_date: date | None = None
    items: list[ExpenseOut]
