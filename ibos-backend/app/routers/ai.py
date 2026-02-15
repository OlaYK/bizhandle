from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security_current import get_current_business
from app.schemas.ai import AIAskIn, AIResponseOut, AITokenUsageOut
from app.services.ai_service import answer_business_question, generate_insight

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/ask", response_model=AIResponseOut)
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


@router.get("/insights/daily", response_model=AIResponseOut)
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
