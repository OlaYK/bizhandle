from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator
from typing import Optional

class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    business_name: Optional[str] = None
    username: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("full_name is required")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value

    @field_validator("business_name")
    @classmethod
    def normalize_business_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "owner@example.com",
                "full_name": "Jane Owner",
                "password": "password123",
                "business_name": "Jane Fabrics",
                "username": "jane_owner",
            }
        }
    )


class RegisterWithInviteIn(BaseModel):
    invitation_token: str
    email: EmailStr
    full_name: str
    password: str
    username: Optional[str] = None

    @field_validator("invitation_token")
    @classmethod
    def validate_invitation_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("invitation_token is required")
        return cleaned

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("full_name is required")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "invitation_token": "ti_abc123",
                "email": "staff@example.com",
                "full_name": "Jane Staff",
                "password": "password123",
                "username": "jane_staff",
            }
        }
    )

class LoginIn(BaseModel):
    identifier: str
    password: str

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("identifier is required")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "identifier": "owner@example.com",
                "password": "password123",
            }
        }
    )


class GoogleAuthIn(BaseModel):
    id_token: str
    business_name: Optional[str] = None
    username: Optional[str] = None

    @field_validator("id_token")
    @classmethod
    def validate_id_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("id_token is required")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_token": "google-id-token-here",
                "business_name": "Jane Fabrics",
                "username": "jane_owner",
            }
        }
    )

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("refresh_token is required")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"refresh_token": "paste-refresh-token-here"}
        }
    )


class LogoutIn(BaseModel):
    refresh_token: str

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("refresh_token is required")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"refresh_token": "paste-refresh-token-here"}
        }
    )


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("current_password is required")
        return cleaned

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("new_password must be at least 8 characters")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "password123",
                "new_password": "new-password-456",
            }
        }
    )


class UserProfileOut(BaseModel):
    id: str
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    business_name: Optional[str] = None
    pending_order_timeout_minutes: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "abc123",
                "email": "owner@example.com",
                "username": "jane_owner",
                "full_name": "Jane Owner",
                "business_name": "Jane Fabrics",
                "pending_order_timeout_minutes": 60,
                "created_at": "2026-02-01T12:00:00Z",
                "updated_at": "2026-02-01T12:00:00Z",
            }
        }
    )


class UpdateProfileIn(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    business_name: Optional[str] = None
    pending_order_timeout_minutes: Optional[int] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("full_name cannot be empty")
        return cleaned

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("username cannot be empty")
        return cleaned

    @field_validator("business_name")
    @classmethod
    def validate_business_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("business_name cannot be empty")
        return cleaned

    @field_validator("pending_order_timeout_minutes")
    @classmethod
    def validate_pending_order_timeout_minutes(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 1:
            raise ValueError("pending_order_timeout_minutes must be at least 1")
        return value

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "UpdateProfileIn":
        if (
            self.full_name is None
            and self.username is None
            and self.business_name is None
            and self.pending_order_timeout_minutes is None
        ):
            raise ValueError("At least one field must be provided")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jane Updated",
                "username": "jane_updated",
                "business_name": "Jane Fabrics Pro",
                "pending_order_timeout_minutes": 120,
            }
        }
    )
