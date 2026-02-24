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
    integration_outbox_max_attempts: int = Field(default=5, ge=1, le=20)
    integration_outbox_retry_seconds: int = Field(default=300, ge=1, le=86400)

    # INVENTORY
    low_stock_default_threshold: int = Field(default=5, ge=0)
    orders_pending_timeout_minutes: int = Field(default=60, ge=1)

    # CORS
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

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

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,
    )


settings = Settings()
