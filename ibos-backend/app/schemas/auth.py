from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
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
