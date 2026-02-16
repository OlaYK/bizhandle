from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.security_current import get_current_business
from app.schemas.ai import AIAskIn, AIResponseOut, AITokenUsageOut
from app.services.ai_service import answer_business_question, generate_insight

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/ask",
    response_model=AIResponseOut,
    summary="Ask AI about your business",
    responses={
        200: {
            "description": "AI answer",
            "content": {
                "application/json": {
                    "example": {
                        "id": "log-id",
                        "insight_type": "question_answer",
                        "response": "Simple profit is 850.00 (sales 1200.00 minus expenses 350.00).",
                        "provider": "local:stub",
                        "model": "ibos-rule-v1",
                        "token_usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 25,
                            "total_tokens": 125,
                        },
                        "estimated_cost_usd": 0.0,
                    }
                }
            },
        },
        **error_responses(400, 401, 404, 422, 500),
    },
)
def ask_business_question(
    payload: AIAskIn,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    try:
        result = answer_business_question(db, business_id=biz.id, question=payload.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(result.log)
    db.commit()
    db.refresh(result.log)

    return AIResponseOut(
        id=result.log.id,
        insight_type=result.log.insight_type,
        response=result.response,
        provider=result.log.provider,
        model=result.log.model,
        token_usage=AITokenUsageOut(
            prompt_tokens=result.log.prompt_tokens,
            completion_tokens=result.log.completion_tokens,
            total_tokens=result.log.total_tokens,
        ),
        estimated_cost_usd=result.log.estimated_cost_usd,
    )


@router.get(
    "/insights/daily",
    response_model=AIResponseOut,
    summary="Generate daily AI insight",
    responses={
        200: {
            "description": "Daily AI insight",
            "content": {
                "application/json": {
                    "example": {
                        "id": "log-id",
                        "insight_type": "daily_insight",
                        "response": "- Profit is 850.00 on sales of 1200.00...\n- Top channel is whatsapp...\n- Top payment method is transfer...",
                        "provider": "local:stub",
                        "model": "ibos-rule-v1",
                        "token_usage": {
                            "prompt_tokens": 90,
                            "completion_tokens": 40,
                            "total_tokens": 130,
                        },
                        "estimated_cost_usd": 0.0,
                    }
                }
            },
        },
        **error_responses(400, 401, 404, 422, 500),
    },
)
def get_daily_insight(
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    try:
        result = generate_insight(db, business_id=biz.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(result.log)
    db.commit()
    db.refresh(result.log)

    return AIResponseOut(
        id=result.log.id,
        insight_type=result.log.insight_type,
        response=result.response,
        provider=result.log.provider,
        model=result.log.model,
        token_usage=AITokenUsageOut(
            prompt_tokens=result.log.prompt_tokens,
            completion_tokens=result.log.completion_tokens,
            total_tokens=result.log.total_tokens,
        ),
        estimated_cost_usd=result.log.estimated_cost_usd,
    )
