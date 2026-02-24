from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CreditMetricOut(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)


class CreditProfileOut(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    grade: str
    metrics: list[CreditMetricOut]
    recommendations: list[str]

    sales_total: float
    expense_total: float
    profit_simple: float
    sales_count: int
    expense_count: int
    low_stock_count: int
    payment_methods_count: int
    start_date: date | None = None
    end_date: date | None = None

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class CreditScoreFactorOut(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    current_value: float
    previous_value: float
    delta_pct: float
    trend: str
    rationale: str


class CreditProfileV2Out(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    grade: str
    factors: list[CreditScoreFactorOut]
    recommendations: list[str]

    current_window_start_date: date
    current_window_end_date: date
    previous_window_start_date: date
    previous_window_end_date: date

    current_net_sales: float
    current_expenses_total: float
    current_net_cashflow: float
    generated_at: datetime


class CashflowForecastIntervalOut(BaseModel):
    interval_index: int = Field(ge=1)
    interval_start_date: date
    interval_end_date: date
    projected_inflow: float
    projected_outflow: float
    projected_net_cashflow: float
    net_lower_bound: float
    net_upper_bound: float


class CashflowForecastOut(BaseModel):
    horizon_days: int = Field(ge=7, le=180)
    history_days: int = Field(ge=30, le=365)
    interval_days: int = Field(ge=7, le=30)
    error_bound_pct: float = Field(ge=0, le=100)
    baseline_daily_net: float
    intervals: list[CashflowForecastIntervalOut]
    generated_at: datetime


class CreditScenarioSimulateIn(BaseModel):
    horizon_days: int = Field(default=30, ge=7, le=180)
    history_days: int = Field(default=90, ge=30, le=365)
    interval_days: int = Field(default=7, ge=7, le=30)
    price_change_pct: float = Field(default=0.0, ge=-0.5, le=1.0)
    expense_change_pct: float = Field(default=0.0, ge=-0.5, le=1.0)
    restock_investment: float = Field(default=0.0, ge=0, le=1_000_000)
    restock_return_multiplier: float = Field(default=1.2, ge=0, le=5.0)


class CreditScenarioOutcomeOut(BaseModel):
    label: str
    projected_revenue: float
    projected_expenses: float
    projected_net_cashflow: float
    projected_margin_pct: float
    intervals: list[CashflowForecastIntervalOut]


class CreditScenarioDeltaOut(BaseModel):
    revenue_delta: float
    expenses_delta: float
    net_cashflow_delta: float
    margin_delta_pct: float


class CreditScenarioSimulationOut(BaseModel):
    baseline: CreditScenarioOutcomeOut
    scenario: CreditScenarioOutcomeOut
    delta: CreditScenarioDeltaOut
    assumptions_json: dict[str, float]
    generated_at: datetime


class LenderPackStatementPeriodOut(BaseModel):
    period_label: str
    period_start_date: date
    period_end_date: date
    net_sales: float
    expenses_total: float
    net_cashflow: float


class LenderExportPackOut(BaseModel):
    pack_id: str
    generated_at: datetime
    window_days: int
    horizon_days: int
    profile: CreditProfileV2Out
    forecast: CashflowForecastOut
    statement_periods: list[LenderPackStatementPeriodOut]
    score_explanation: list[str]
    recommendations: list[str]
    bundle_sections: list[str]


class FinanceGuardrailPolicyIn(BaseModel):
    enabled: bool = True
    margin_floor_ratio: float = Field(default=0.15, ge=-1, le=1)
    margin_drop_threshold: float = Field(default=0.08, ge=0, le=1)
    expense_growth_threshold: float = Field(default=0.25, ge=0, le=5)
    minimum_cash_buffer: float = Field(default=0, ge=0, le=10_000_000)


class FinanceGuardrailPolicyOut(BaseModel):
    id: str
    enabled: bool
    margin_floor_ratio: float
    margin_drop_threshold: float
    expense_growth_threshold: float
    minimum_cash_buffer: float
    updated_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class FinanceGuardrailAlertOut(BaseModel):
    alert_type: str
    severity: str
    message: str
    current_value: float
    threshold_value: float
    delta_value: float
    window_start_date: date
    window_end_date: date


class FinanceGuardrailEvaluationOut(BaseModel):
    policy: FinanceGuardrailPolicyOut
    alerts: list[FinanceGuardrailAlertOut]
    generated_at: datetime


class CreditImprovementActionOut(BaseModel):
    priority: int = Field(ge=1)
    factor_key: str
    factor_label: str
    title: str
    description: str
    current_score: float
    target_score: float
    estimated_score_impact: float
    measurable_target: str


class CreditImprovementPlanOut(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    target_score: int = Field(ge=0, le=100)
    actions: list[CreditImprovementActionOut]
    generated_at: datetime
