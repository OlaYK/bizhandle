from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional

class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    business_name: str
    username: Optional[str] = None

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


class GoogleAuthIn(BaseModel):
    id_token: str
    business_name: Optional[str] = None
    username: Optional[str] = None

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
