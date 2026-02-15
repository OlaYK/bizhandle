from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IBOS Backend"
    env: str = "dev"
    secret_key: str
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # DATABASE
    database_url: str

    # AI
    ai_provider: str = "stub"
    ai_model: str = "ibos-rule-v1"
    ai_vendor: str = "local"
    ai_temperature: float = 0.2
    ai_max_question_chars: int = 500
    ai_cost_per_1k_tokens_usd: float = 0.0
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # GOOGLE AUTH
    google_client_id: str | None = None

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,
    )


settings = Settings()
