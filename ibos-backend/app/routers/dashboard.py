from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_permission
from app.core.security_current import BusinessAccess, get_current_business, get_current_user
from app.models.user import User
from app.schemas.credit import (
    CashflowForecastOut,
    CreditImprovementPlanOut,
    CreditProfileOut,
    CreditProfileV2Out,
    CreditScenarioSimulateIn,
    CreditScenarioSimulationOut,
    FinanceGuardrailEvaluationOut,
    FinanceGuardrailPolicyIn,
    FinanceGuardrailPolicyOut,
    LenderExportPackOut,
)
from app.schemas.dashboard import DashboardCustomerInsightsOut, DashboardSummaryOut
from app.services.credit_service import (
    build_credit_improvement_plan,
    finance_guardrail_policy_out,
    generate_lender_export_pack,
    get_cashflow_forecast,
    get_credit_profile,
    get_credit_profile_v2,
    get_finance_guardrail_evaluation,
    get_or_create_finance_guardrail_policy,
    simulate_credit_scenario,
    update_finance_guardrail_policy,
)
from app.services.dashboard_service import get_customer_insights, get_summary
from app.services.pdf_export_service import build_text_pdf

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummaryOut,
    summary="Get KPI summary",
    responses={
        200: {
            "description": "Dashboard summary",
            "content": {
                "application/json": {
                    "example": {
                        "sales_total": 1200.0,
                        "sales_count": 10,
                        "average_sale_value": 120.0,
                        "expense_total": 350.0,
                        "expense_count": 5,
                        "profit_simple": 850.0,
                        "start_date": None,
                        "end_date": None,
                    }
                }
            },
        },
        **error_responses(400, 401, 404, 422, 500),
    },
)
def summary(
    start_date: date | None = Query(default=None, description="Filter from date (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="Filter to date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")
    return get_summary(db, biz.id, start_date=start_date, end_date=end_date)


@router.get(
    "/customer-insights",
    response_model=DashboardCustomerInsightsOut,
    summary="Get customer insights summary",
    responses={
        200: {
            "description": "Customer-level dashboard insights",
            "content": {
                "application/json": {
                    "example": {
                        "repeat_buyers": 4,
                        "active_customers": 12,
                        "total_customers": 30,
                        "top_customers": [
                            {
                                "customer_id": "customer-id",
                                "customer_name": "Aisha Bello",
                                "total_spent": 1200.0,
                                "transactions": 5,
                            }
                        ],
                        "start_date": None,
                        "end_date": None,
                    }
                }
            },
        },
        **error_responses(400, 401, 404, 422, 500),
    },
)
def customer_insights(
    start_date: date | None = Query(default=None, description="Filter from date (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="Filter to date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")
    return get_customer_insights(db, biz.id, start_date=start_date, end_date=end_date)


@router.get(
    "/credit-profile",
    response_model=CreditProfileOut,
    summary="Get business credit profile",
    responses={
        200: {
            "description": "Business credit profile breakdown",
            "content": {
                "application/json": {
                    "example": {
                        "overall_score": 74,
                        "grade": "good",
                        "metrics": [
                            {"name": "Profitability", "score": 68.5},
                            {"name": "Revenue", "score": 80.0},
                            {"name": "Cost Control", "score": 72.0},
                            {"name": "Inventory", "score": 65.0},
                            {"name": "Payment Mix", "score": 66.7},
                        ],
                        "recommendations": [
                            "Increase average ticket size by bundling high-margin variants."
                        ],
                        "sales_total": 1200.0,
                        "expense_total": 350.0,
                        "profit_simple": 850.0,
                        "sales_count": 10,
                        "expense_count": 5,
                        "low_stock_count": 3,
                        "payment_methods_count": 2,
                        "start_date": None,
                        "end_date": None,
                    }
                }
            },
        },
        **error_responses(400, 401, 404, 422, 500),
    },
)
def credit_profile(
    start_date: date | None = Query(default=None, description="Filter from date (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="Filter to date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")
    return get_credit_profile(db, biz.id, start_date=start_date, end_date=end_date)


@router.get(
    "/credit-profile/v2",
    response_model=CreditProfileV2Out,
    summary="Get business credit profile v2 with trend-based explainable factors",
    responses=error_responses(401, 403, 422, 500),
)
def credit_profile_v2(
    window_days: int = Query(default=30, ge=14, le=90),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.profile.v2.view")),
):
    return get_credit_profile_v2(
        db,
        business_id=access.business.id,
        window_days=window_days,
    )


@router.get(
    "/credit-forecast",
    response_model=CashflowForecastOut,
    summary="Get short/medium-horizon cashflow forecast intervals and error bounds",
    responses=error_responses(401, 403, 422, 500),
)
def credit_forecast(
    horizon_days: int = Query(default=30, ge=7, le=180),
    history_days: int = Query(default=90, ge=30, le=365),
    interval_days: int = Query(default=7, ge=7, le=30),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.forecast.view")),
):
    return get_cashflow_forecast(
        db,
        business_id=access.business.id,
        horizon_days=horizon_days,
        history_days=history_days,
        interval_days=interval_days,
    )


@router.post(
    "/credit-scenarios/simulate",
    response_model=CreditScenarioSimulationOut,
    summary="Simulate pricing, expense, and restock what-if scenarios",
    responses=error_responses(401, 403, 422, 500),
)
def credit_scenario_simulate(
    payload: CreditScenarioSimulateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.scenario.simulate")),
):
    return simulate_credit_scenario(
        db,
        business_id=access.business.id,
        payload=payload,
    )


@router.post(
    "/credit-export-pack",
    response_model=LenderExportPackOut,
    summary="Generate lender-ready export pack",
    responses=error_responses(401, 403, 422, 500),
)
def credit_export_pack(
    window_days: int = Query(default=30, ge=14, le=90),
    history_days: int = Query(default=120, ge=30, le=365),
    horizon_days: int = Query(default=90, ge=30, le=180),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.export_pack.generate")),
):
    return generate_lender_export_pack(
        db,
        business_id=access.business.id,
        window_days=window_days,
        history_days=history_days,
        horizon_days=horizon_days,
    )


@router.get(
    "/credit-export-pack/download",
    summary="Download lender export pack as PDF",
    responses=error_responses(401, 403, 422, 500),
)
def credit_export_pack_download(
    window_days: int = Query(default=30, ge=14, le=90),
    history_days: int = Query(default=120, ge=30, le=365),
    horizon_days: int = Query(default=90, ge=30, le=180),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.export_pack.generate")),
):
    pack = generate_lender_export_pack(
        db,
        business_id=access.business.id,
        window_days=window_days,
        history_days=history_days,
        horizon_days=horizon_days,
    )

    lines: list[str] = [
        f"Pack ID: {pack.pack_id}",
        f"Business ID: {access.business.id}",
        f"Window Days: {pack.window_days}",
        f"Horizon Days: {pack.horizon_days}",
        f"Overall Score: {pack.profile.overall_score} ({pack.profile.grade})",
        f"Current Net Sales: {pack.profile.current_net_sales:.2f}",
        f"Current Expenses: {pack.profile.current_expenses_total:.2f}",
        f"Current Net Cashflow: {pack.profile.current_net_cashflow:.2f}",
        "",
        "Top Factors:",
    ]
    for factor in pack.profile.factors[:8]:
        lines.append(
            f"- {factor.label}: score={factor.score:.2f}, weight={factor.weight:.2f}, trend={factor.trend}"
        )

    lines.append("")
    lines.append("Recommendations:")
    for recommendation in pack.recommendations[:10]:
        lines.append(f"- {recommendation}")

    pdf_bytes = build_text_pdf(
        title="MoniDesk Lender Export Pack",
        lines=lines,
        generated_at=pack.generated_at,
    )
    filename = f"lender-pack-{pack.pack_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/finance-guardrails/policy",
    response_model=FinanceGuardrailPolicyOut,
    summary="Get finance guardrail policy",
    responses=error_responses(401, 403, 500),
)
def get_finance_guardrail_policy(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.guardrails.view")),
):
    policy = get_or_create_finance_guardrail_policy(
        db,
        business_id=access.business.id,
        actor_user_id=None,
    )
    db.commit()
    db.refresh(policy)
    return finance_guardrail_policy_out(policy)


@router.put(
    "/finance-guardrails/policy",
    response_model=FinanceGuardrailPolicyOut,
    summary="Update finance guardrail policy",
    responses=error_responses(401, 403, 422, 500),
)
def put_finance_guardrail_policy(
    payload: FinanceGuardrailPolicyIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.guardrails.manage")),
    actor: User = Depends(get_current_user),
):
    policy = update_finance_guardrail_policy(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        payload=payload,
    )
    db.commit()
    db.refresh(policy)
    return finance_guardrail_policy_out(policy)


@router.post(
    "/finance-guardrails/evaluate",
    response_model=FinanceGuardrailEvaluationOut,
    summary="Evaluate finance guardrail alerts",
    responses=error_responses(401, 403, 422, 500),
)
def evaluate_finance_guardrails_endpoint(
    window_days: int = Query(default=30, ge=14, le=90),
    history_days: int = Query(default=90, ge=30, le=365),
    horizon_days: int = Query(default=30, ge=7, le=180),
    interval_days: int = Query(default=7, ge=7, le=30),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.guardrails.view")),
    actor: User = Depends(get_current_user),
):
    evaluation = get_finance_guardrail_evaluation(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        window_days=window_days,
        history_days=history_days,
        horizon_days=horizon_days,
        interval_days=interval_days,
    )
    db.commit()
    return evaluation


@router.get(
    "/credit-improvement-plan",
    response_model=CreditImprovementPlanOut,
    summary="Get prioritized credit improvement action plan",
    responses=error_responses(401, 403, 422, 500),
)
def credit_improvement_plan(
    window_days: int = Query(default=30, ge=14, le=90),
    target_score: int = Query(default=80, ge=50, le=100),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("credit.improvement.plan.view")),
):
    return build_credit_improvement_plan(
        db,
        business_id=access.business.id,
        window_days=window_days,
        target_score=target_score,
    )
