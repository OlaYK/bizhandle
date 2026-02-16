from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AIAskIn(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question cannot be empty")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What is my current profit and one action to improve it this week?"
            }
        }
    )


class AITokenUsageOut(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class AIResponseOut(BaseModel):
    id: str
    insight_type: str
    response: str
    provider: str
    model: str
    token_usage: Optional[AITokenUsageOut] = None
    estimated_cost_usd: Optional[float] = None
