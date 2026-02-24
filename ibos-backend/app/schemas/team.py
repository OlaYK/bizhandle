from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.schemas.common import PaginationMeta

ALLOWED_TEAM_ROLES = {"owner", "admin", "staff"}


class TeamMemberCreateIn(BaseModel):
    email: EmailStr
    role: str = "staff"

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in ALLOWED_TEAM_ROLES:
            raise ValueError("role must be one of: owner, admin, staff")
        return role

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "staff@example.com",
                "role": "staff",
            }
        }
    )


class TeamMemberUpdateIn(BaseModel):
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        role = value.strip().lower()
        if role not in ALLOWED_TEAM_ROLES:
            raise ValueError("role must be one of: owner, admin, staff")
        return role

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "TeamMemberUpdateIn":
        if self.role is None and self.is_active is None:
            raise ValueError("At least one field must be provided")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "admin",
                "is_active": True,
            }
        }
    )


class TeamMemberOut(BaseModel):
    membership_id: str
    user_id: str
    email: EmailStr
    username: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class TeamMemberListOut(BaseModel):
    items: list[TeamMemberOut]
    pagination: PaginationMeta


class TeamInvitationCreateIn(BaseModel):
    email: EmailStr
    role: str = "staff"
    expires_in_days: int = 7

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in ALLOWED_TEAM_ROLES:
            raise ValueError("role must be one of: owner, admin, staff")
        return role

    @field_validator("expires_in_days")
    @classmethod
    def validate_expiry_window(cls, value: int) -> int:
        if value < 1 or value > 30:
            raise ValueError("expires_in_days must be between 1 and 30")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "new.staff@example.com",
                "role": "staff",
                "expires_in_days": 7,
            }
        }
    )


class TeamInvitationOut(BaseModel):
    invitation_id: str
    business_id: str
    invited_by_user_id: str
    accepted_by_user_id: str | None = None
    email: EmailStr
    role: str
    status: str
    expires_at: datetime
    invited_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None


class TeamInvitationCreateOut(TeamInvitationOut):
    invitation_token: str


class TeamInvitationListOut(BaseModel):
    items: list[TeamInvitationOut]
    pagination: PaginationMeta


class TeamInvitationAcceptIn(BaseModel):
    invitation_token: str

    @field_validator("invitation_token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("invitation_token is required")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"invitation_token": "ti_abc123"},
        }
    )
