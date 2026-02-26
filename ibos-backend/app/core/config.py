import json
from typing import List, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MoniDesk Backend"
    env: str = "dev"
    secret_key: str
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # DATABASE
    database_url: str
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    db_pool_recycle_seconds: int = Field(default=1800, ge=30, le=86_400)

    # AI
    ai_provider: str = "stub"
    ai_model: str = "monidesk-rule-v1"
    ai_vendor: str = "local"
    ai_temperature: float = 0.2
    ai_max_question_chars: int = 500
    ai_cost_per_1k_tokens_usd: float = 0.0
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # GOOGLE AUTH
    google_client_id: str | None = None

    # AUTH HARDENING
    auth_rate_limit_max_attempts: int = Field(default=5, ge=1)
    auth_rate_limit_window_seconds: int = Field(default=300, ge=1)
    auth_rate_limit_lock_seconds: int = Field(default=900, ge=1)
    storefront_public_rate_limit_requests: int = Field(default=120, ge=1)
    storefront_public_rate_limit_window_seconds: int = Field(default=60, ge=1)
    payment_provider_default: str = "stub"
    payment_webhook_secret: str = "dev-webhook-secret"
    checkout_retry_expiry_extension_minutes: int = Field(default=30, ge=1, le=10080)
    shipping_provider_default: str = "stub_carrier"
    messaging_provider_default: str = "whatsapp_stub"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender_email: str | None = None
    smtp_reply_to_email: str | None = None
    smtp_use_starttls: bool = True
    smtp_use_ssl: bool = False
    team_invite_web_base_url: str | None = None
    integration_outbox_max_attempts: int = Field(default=5, ge=1, le=20)
    integration_outbox_retry_seconds: int = Field(default=300, ge=1, le=86400)
    api_timeout_hint_ms: int = Field(default=300000, ge=1000, le=1_800_000)

    # INVENTORY
    low_stock_default_threshold: int = Field(default=5, ge=0)
    orders_pending_timeout_minutes: int = Field(default=60, ge=1)

    # CORS
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    cors_origin_regex: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            if not v.strip():
                return []
            if v.startswith("["):
                parsed = json.loads(v)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON value must be a list")
                return [str(i).strip() for i in parsed if str(i).strip()]
            if not v.startswith("["):
                return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        raise ValueError(v)

    @field_validator(
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "smtp_sender_email",
        "smtp_reply_to_email",
        "team_invite_web_base_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        env_value = self.env.lower().strip()
        if env_value not in {"prod", "production"}:
            return self

        weak_secrets = {
            "",
            "change_me",
            "change_me_please_to_a_long_random_string",
            "dev-secret-key-change-before-prod",
        }
        if self.secret_key.strip() in weak_secrets or len(self.secret_key.strip()) < 32:
            raise ValueError("SECRET_KEY must be a strong random value in production")

        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS cannot contain '*' in production")
        if self.cors_origin_regex:
            raise ValueError("CORS_ORIGIN_REGEX cannot be set in production")

        if self.smtp_use_ssl and self.smtp_use_starttls:
            raise ValueError("Set only one of SMTP_USE_SSL or SMTP_USE_STARTTLS in production")

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,
    )


settings = Settings()
