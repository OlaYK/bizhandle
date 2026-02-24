from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from math import sqrt
from statistics import fmean, pstdev
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.money import ZERO_MONEY, to_money
from app.models.credit_intelligence import FinanceGuardrailPolicy
from app.models.expense import Expense
from app.models.inventory import InventoryLedger
from app.models.product import ProductVariant
from app.models.sales import Sale
from app.schemas.credit import (
    CashflowForecastIntervalOut,
    CashflowForecastOut,
    CreditImprovementActionOut,
    CreditImprovementPlanOut,
    CreditMetricOut,
    CreditProfileOut,
    CreditProfileV2Out,
    FinanceGuardrailAlertOut,
    FinanceGuardrailEvaluationOut,
    FinanceGuardrailPolicyIn,
    FinanceGuardrailPolicyOut,
    LenderExportPackOut,
    LenderPackStatementPeriodOut,
    CreditScenarioDeltaOut,
    CreditScenarioOutcomeOut,
    CreditScenarioSimulateIn,
    CreditScenarioSimulationOut,
    CreditScoreFactorOut,
)


@dataclass
class DailyCashflowSeries:
    dates: list[date]
    inflows: list[float]
    outflows: list[float]
    nets: list[float]


@dataclass
class WindowFinancials:
    start_date: date
    end_date: date
    sales_total: float
    refunds_total_abs: float
    net_sales: float
    expenses_total: float
    sale_count: int
    refund_count: int
    payment_methods_count: int
    daily_net_values: list[float]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _grade(score: int) -> str:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 55:
        return "fair"
    return "weak"


def _recommendations(metrics: list[CreditMetricOut]) -> list[str]:
    low_metrics = [metric for metric in metrics if metric.score < 60]
    recs: list[str] = []
    for metric in low_metrics:
        if metric.name == "Profitability":
            recs.append("Increase average ticket size by bundling high-margin variants.")
        elif metric.name == "Revenue":
            recs.append("Stabilize weekly sales cadence with channel-specific campaigns.")
        elif metric.name == "Cost Control":
            recs.append("Cap discretionary expenses and tie spend to active sales campaigns.")
        elif metric.name == "Inventory":
            recs.append("Restock low-stock variants to reduce potential stock-outs.")
        elif metric.name == "Payment Mix":
            recs.append("Diversify payment options to reduce collection friction.")

    if not recs:
        recs.append("Maintain current discipline and monitor profitability weekly.")
    return recs


def _financial_base_statements(
    *,
    business_id: str,
    start_date: date | None,
    end_date: date | None,
):
    sales_total_stmt = select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
        Sale.business_id == business_id
    )
    sales_count_stmt = select(func.count(Sale.id)).where(
        Sale.business_id == business_id,
        Sale.kind == "sale",
    )
    expense_total_stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.business_id == business_id
    )
    expense_count_stmt = select(func.count(Expense.id)).where(Expense.business_id == business_id)
    payment_method_count_stmt = select(func.count(func.distinct(Sale.payment_method))).where(
        Sale.business_id == business_id,
        Sale.kind == "sale",
    )

    if start_date:
        sales_total_stmt = sales_total_stmt.where(func.date(Sale.created_at) >= start_date)
        sales_count_stmt = sales_count_stmt.where(func.date(Sale.created_at) >= start_date)
        expense_total_stmt = expense_total_stmt.where(func.date(Expense.created_at) >= start_date)
        expense_count_stmt = expense_count_stmt.where(func.date(Expense.created_at) >= start_date)
        payment_method_count_stmt = payment_method_count_stmt.where(
            func.date(Sale.created_at) >= start_date
        )
    if end_date:
        sales_total_stmt = sales_total_stmt.where(func.date(Sale.created_at) <= end_date)
        sales_count_stmt = sales_count_stmt.where(func.date(Sale.created_at) <= end_date)
        expense_total_stmt = expense_total_stmt.where(func.date(Expense.created_at) <= end_date)
        expense_count_stmt = expense_count_stmt.where(func.date(Expense.created_at) <= end_date)
        payment_method_count_stmt = payment_method_count_stmt.where(
            func.date(Sale.created_at) <= end_date
        )

    return (
        sales_total_stmt,
        sales_count_stmt,
        expense_total_stmt,
        expense_count_stmt,
        payment_method_count_stmt,
    )


def _low_stock_count(db: Session, *, business_id: str) -> int:
    variants = db.execute(
        select(ProductVariant.id, ProductVariant.reorder_level).where(
            ProductVariant.business_id == business_id
        )
    ).all()
    if not variants:
        return 0

    variant_ids = [row[0] for row in variants]
    stock_rows = db.execute(
        select(
            InventoryLedger.variant_id,
            func.coalesce(func.sum(InventoryLedger.qty_delta), 0),
        )
        .where(
            InventoryLedger.business_id == business_id,
            InventoryLedger.variant_id.in_(variant_ids),
        )
        .group_by(InventoryLedger.variant_id)
    ).all()
    stock_by_variant = {variant_id: int(stock) for variant_id, stock in stock_rows}

    default_threshold = settings.low_stock_default_threshold
    low_count = 0
    for variant_id, reorder_level in variants:
        threshold = reorder_level if reorder_level > 0 else default_threshold
        if stock_by_variant.get(variant_id, 0) <= threshold:
            low_count += 1
    return low_count


def get_credit_profile(
    db: Session,
    business_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> CreditProfileOut:
    (
        sales_total_stmt,
        sales_count_stmt,
        expense_total_stmt,
        expense_count_stmt,
        payment_method_count_stmt,
    ) = _financial_base_statements(
        business_id=business_id,
        start_date=start_date,
        end_date=end_date,
    )

    sales_total_raw = db.execute(sales_total_stmt).scalar_one() or ZERO_MONEY
    sales_count = int(db.execute(sales_count_stmt).scalar_one() or 0)
    expense_total_raw = db.execute(expense_total_stmt).scalar_one() or ZERO_MONEY
    expense_count = int(db.execute(expense_count_stmt).scalar_one() or 0)
    payment_methods_count = int(db.execute(payment_method_count_stmt).scalar_one() or 0)
    low_stock_count = _low_stock_count(db, business_id=business_id)

    sales_total = to_money(sales_total_raw)
    expense_total = to_money(expense_total_raw)
    profit_simple: Decimal = to_money(sales_total - expense_total)

    profit_margin = float((profit_simple / sales_total) if sales_total else ZERO_MONEY)
    expense_ratio = float((expense_total / sales_total) if sales_total else Decimal("1"))

    profitability = _clamp(profit_margin * 100)
    revenue_consistency = _clamp((sales_count / 40.0) * 100)
    cost_discipline = _clamp((1 - expense_ratio) * 100)
    inventory_health = _clamp(
        (1 - (low_stock_count / max(10.0, low_stock_count + 4.0))) * 100
    )
    payment_diversity = _clamp((payment_methods_count / 3.0) * 100)

    metrics = [
        CreditMetricOut(name="Profitability", score=round(profitability, 2)),
        CreditMetricOut(name="Revenue", score=round(revenue_consistency, 2)),
        CreditMetricOut(name="Cost Control", score=round(cost_discipline, 2)),
        CreditMetricOut(name="Inventory", score=round(inventory_health, 2)),
        CreditMetricOut(name="Payment Mix", score=round(payment_diversity, 2)),
    ]

    weighted_score = (
        metrics[0].score * 0.30
        + metrics[1].score * 0.20
        + metrics[2].score * 0.20
        + metrics[3].score * 0.20
        + metrics[4].score * 0.10
    )
    overall_score = int(round(_clamp(weighted_score)))

    return CreditProfileOut(
        overall_score=overall_score,
        grade=_grade(overall_score),
        metrics=metrics,
        recommendations=_recommendations(metrics),
        sales_total=float(sales_total),
        expense_total=float(expense_total),
        profit_simple=float(profit_simple),
        sales_count=sales_count,
        expense_count=expense_count,
        low_stock_count=low_stock_count,
        payment_methods_count=payment_methods_count,
        start_date=start_date,
        end_date=end_date,
    )


def get_credit_profile_v2(
    db: Session,
    *,
    business_id: str,
    window_days: int = 30,
) -> CreditProfileV2Out:
    normalized_window_days = max(14, min(int(window_days), 90))
    current_end_date = date.today()
    current_start_date = current_end_date - timedelta(days=normalized_window_days - 1)
    previous_end_date = current_start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=normalized_window_days - 1)

    current = _window_financials(
        db,
        business_id=business_id,
        start_date=current_start_date,
        end_date=current_end_date,
    )
    previous = _window_financials(
        db,
        business_id=business_id,
        start_date=previous_start_date,
        end_date=previous_end_date,
    )
    factors = _build_credit_factors(current=current, previous=previous)
    overall_score = int(round(_clamp(sum(item.score * item.weight for item in factors))))

    current_net_cashflow = current.net_sales - current.expenses_total
    return CreditProfileV2Out(
        overall_score=overall_score,
        grade=_grade(overall_score),
        factors=factors,
        recommendations=_factor_recommendations(factors),
        current_window_start_date=current.start_date,
        current_window_end_date=current.end_date,
        previous_window_start_date=previous.start_date,
        previous_window_end_date=previous.end_date,
        current_net_sales=round(current.net_sales, 2),
        current_expenses_total=round(current.expenses_total, 2),
        current_net_cashflow=round(current_net_cashflow, 2),
        generated_at=datetime.now(timezone.utc),
    )


def get_cashflow_forecast(
    db: Session,
    *,
    business_id: str,
    horizon_days: int = 30,
    history_days: int = 90,
    interval_days: int = 7,
) -> CashflowForecastOut:
    normalized_horizon_days = max(7, min(int(horizon_days), 180))
    normalized_history_days = max(30, min(int(history_days), 365))
    normalized_interval_days = max(7, min(int(interval_days), 30))

    history_end_date = date.today()
    history_start_date = history_end_date - timedelta(days=normalized_history_days - 1)
    series = _historical_cashflow_series(
        db,
        business_id=business_id,
        start_date=history_start_date,
        end_date=history_end_date,
    )

    baseline_inflow = fmean(series.inflows) if series.inflows else 0.0
    baseline_outflow = fmean(series.outflows) if series.outflows else 0.0
    baseline_daily_net = fmean(series.nets) if series.nets else 0.0
    inflow_slope = _linear_slope(series.inflows)
    outflow_slope = _linear_slope(series.outflows)
    volatility = pstdev(series.nets) if len(series.nets) > 1 else 0.0
    error_bound_pct = _clamp(
        (volatility / max(abs(baseline_daily_net), 1.0)) * 100,
        minimum=5.0,
        maximum=60.0,
    )

    daily_forecast: list[tuple[date, float, float, float, float, float]] = []
    for day_index in range(1, normalized_horizon_days + 1):
        projected_inflow = max(0.0, baseline_inflow + inflow_slope * day_index)
        projected_outflow = max(0.0, baseline_outflow + outflow_slope * day_index)
        projected_net = projected_inflow - projected_outflow

        growth_factor = sqrt(day_index / max(normalized_interval_days, 1))
        net_error_band = abs(projected_net) * (error_bound_pct / 100.0) + volatility * 0.35 * growth_factor
        net_lower_bound = projected_net - net_error_band
        net_upper_bound = projected_net + net_error_band

        daily_forecast.append(
            (
                history_end_date + timedelta(days=day_index),
                projected_inflow,
                projected_outflow,
                projected_net,
                net_lower_bound,
                net_upper_bound,
            )
        )

    intervals: list[CashflowForecastIntervalOut] = []
    for start_index in range(0, len(daily_forecast), normalized_interval_days):
        chunk = daily_forecast[start_index : start_index + normalized_interval_days]
        if not chunk:
            continue
        projected_inflow = round(sum(item[1] for item in chunk), 2)
        projected_outflow = round(sum(item[2] for item in chunk), 2)
        projected_net_cashflow = round(sum(item[3] for item in chunk), 2)
        net_lower_bound = round(sum(item[4] for item in chunk), 2)
        net_upper_bound = round(sum(item[5] for item in chunk), 2)
        intervals.append(
            CashflowForecastIntervalOut(
                interval_index=len(intervals) + 1,
                interval_start_date=chunk[0][0],
                interval_end_date=chunk[-1][0],
                projected_inflow=projected_inflow,
                projected_outflow=projected_outflow,
                projected_net_cashflow=projected_net_cashflow,
                net_lower_bound=net_lower_bound,
                net_upper_bound=net_upper_bound,
            )
        )

    return CashflowForecastOut(
        horizon_days=normalized_horizon_days,
        history_days=normalized_history_days,
        interval_days=normalized_interval_days,
        error_bound_pct=round(error_bound_pct, 2),
        baseline_daily_net=round(baseline_daily_net, 2),
        intervals=intervals,
        generated_at=datetime.now(timezone.utc),
    )


def simulate_credit_scenario(
    db: Session,
    *,
    business_id: str,
    payload: CreditScenarioSimulateIn,
) -> CreditScenarioSimulationOut:
    baseline_forecast = get_cashflow_forecast(
        db,
        business_id=business_id,
        horizon_days=payload.horizon_days,
        history_days=payload.history_days,
        interval_days=payload.interval_days,
    )

    baseline_intervals = baseline_forecast.intervals
    interval_count = max(len(baseline_intervals), 1)
    restock_cost_per_interval = payload.restock_investment / interval_count
    restock_revenue_per_interval = (
        payload.restock_investment * payload.restock_return_multiplier / interval_count
    )

    scenario_intervals: list[CashflowForecastIntervalOut] = []
    for interval in baseline_intervals:
        projected_inflow = max(
            0.0,
            interval.projected_inflow * (1 + payload.price_change_pct) + restock_revenue_per_interval,
        )
        projected_outflow = max(
            0.0,
            interval.projected_outflow * (1 + payload.expense_change_pct) + restock_cost_per_interval,
        )
        projected_net_cashflow = projected_inflow - projected_outflow
        net_delta = projected_net_cashflow - interval.projected_net_cashflow
        scenario_intervals.append(
            CashflowForecastIntervalOut(
                interval_index=interval.interval_index,
                interval_start_date=interval.interval_start_date,
                interval_end_date=interval.interval_end_date,
                projected_inflow=round(projected_inflow, 2),
                projected_outflow=round(projected_outflow, 2),
                projected_net_cashflow=round(projected_net_cashflow, 2),
                net_lower_bound=round(interval.net_lower_bound + net_delta, 2),
                net_upper_bound=round(interval.net_upper_bound + net_delta, 2),
            )
        )

    baseline_outcome = _scenario_outcome(label="baseline", intervals=baseline_intervals)
    scenario_outcome = _scenario_outcome(label="scenario", intervals=scenario_intervals)
    delta = CreditScenarioDeltaOut(
        revenue_delta=round(
            scenario_outcome.projected_revenue - baseline_outcome.projected_revenue,
            2,
        ),
        expenses_delta=round(
            scenario_outcome.projected_expenses - baseline_outcome.projected_expenses,
            2,
        ),
        net_cashflow_delta=round(
            scenario_outcome.projected_net_cashflow - baseline_outcome.projected_net_cashflow,
            2,
        ),
        margin_delta_pct=round(
            scenario_outcome.projected_margin_pct - baseline_outcome.projected_margin_pct,
            2,
        ),
    )

    return CreditScenarioSimulationOut(
        baseline=baseline_outcome,
        scenario=scenario_outcome,
        delta=delta,
        assumptions_json={
            "price_change_pct": float(payload.price_change_pct),
            "expense_change_pct": float(payload.expense_change_pct),
            "restock_investment": float(payload.restock_investment),
            "restock_return_multiplier": float(payload.restock_return_multiplier),
            "horizon_days": float(payload.horizon_days),
            "history_days": float(payload.history_days),
            "interval_days": float(payload.interval_days),
        },
        generated_at=datetime.now(timezone.utc),
    )


def get_or_create_finance_guardrail_policy(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str | None,
) -> FinanceGuardrailPolicy:
    policy = db.execute(
        select(FinanceGuardrailPolicy).where(FinanceGuardrailPolicy.business_id == business_id)
    ).scalar_one_or_none()
    if policy is None:
        policy = FinanceGuardrailPolicy(
            id=str(uuid.uuid4()),
            business_id=business_id,
            enabled=True,
            margin_floor_ratio=0.15,
            margin_drop_threshold=0.08,
            expense_growth_threshold=0.25,
            minimum_cash_buffer=0,
            updated_by_user_id=actor_user_id,
        )
        db.add(policy)
        db.flush()
    return policy


def update_finance_guardrail_policy(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str,
    payload: FinanceGuardrailPolicyIn,
) -> FinanceGuardrailPolicy:
    policy = get_or_create_finance_guardrail_policy(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
    )
    policy.enabled = bool(payload.enabled)
    policy.margin_floor_ratio = float(payload.margin_floor_ratio)
    policy.margin_drop_threshold = float(payload.margin_drop_threshold)
    policy.expense_growth_threshold = float(payload.expense_growth_threshold)
    policy.minimum_cash_buffer = float(payload.minimum_cash_buffer)
    policy.updated_by_user_id = actor_user_id
    return policy


def evaluate_finance_guardrails(
    db: Session,
    *,
    business_id: str,
    policy: FinanceGuardrailPolicy,
    window_days: int = 30,
    history_days: int = 90,
    horizon_days: int = 30,
    interval_days: int = 7,
) -> list[FinanceGuardrailAlertOut]:
    if not policy.enabled:
        return []

    normalized_window_days = max(14, min(int(window_days), 90))
    current_end_date = date.today()
    current_start_date = current_end_date - timedelta(days=normalized_window_days - 1)
    previous_end_date = current_start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=normalized_window_days - 1)

    current = _window_financials(
        db,
        business_id=business_id,
        start_date=current_start_date,
        end_date=current_end_date,
    )
    previous = _window_financials(
        db,
        business_id=business_id,
        start_date=previous_start_date,
        end_date=previous_end_date,
    )
    forecast = get_cashflow_forecast(
        db,
        business_id=business_id,
        horizon_days=horizon_days,
        history_days=history_days,
        interval_days=interval_days,
    )

    current_margin = (
        (current.net_sales - current.expenses_total) / max(current.net_sales, 1.0)
        if current.net_sales > 0
        else -1.0
    )
    previous_margin = (
        (previous.net_sales - previous.expenses_total) / max(previous.net_sales, 1.0)
        if previous.net_sales > 0
        else -1.0
    )
    margin_drop = previous_margin - current_margin
    expense_growth = _pct_change(current.expenses_total, previous.expenses_total)
    weakest_lower_bound = min(
        (interval.net_lower_bound for interval in forecast.intervals),
        default=0.0,
    )

    alerts: list[FinanceGuardrailAlertOut] = []
    if current_margin <= float(policy.margin_floor_ratio) or margin_drop >= float(policy.margin_drop_threshold):
        alerts.append(
            FinanceGuardrailAlertOut(
                alert_type="margin_collapse",
                severity="high" if current_margin <= 0 or margin_drop >= policy.margin_drop_threshold * 1.5 else "medium",
                message=(
                    f"Margin is {current_margin * 100:.1f}% with a {margin_drop * 100:.1f}% drop from previous window."
                ),
                current_value=round(current_margin, 4),
                threshold_value=round(float(policy.margin_floor_ratio), 4),
                delta_value=round(margin_drop, 4),
                window_start_date=current_start_date,
                window_end_date=current_end_date,
            )
        )

    if expense_growth >= float(policy.expense_growth_threshold):
        alerts.append(
            FinanceGuardrailAlertOut(
                alert_type="expense_spike",
                severity="high" if expense_growth >= policy.expense_growth_threshold * 1.5 else "medium",
                message=(
                    f"Expenses grew {expense_growth * 100:.1f}% window-over-window, above policy threshold."
                ),
                current_value=round(expense_growth, 4),
                threshold_value=round(float(policy.expense_growth_threshold), 4),
                delta_value=round(expense_growth - float(policy.expense_growth_threshold), 4),
                window_start_date=current_start_date,
                window_end_date=current_end_date,
            )
        )

    if weakest_lower_bound <= float(policy.minimum_cash_buffer):
        alerts.append(
            FinanceGuardrailAlertOut(
                alert_type="weak_liquidity",
                severity="high" if weakest_lower_bound < 0 else "medium",
                message=(
                    f"Forecast lower-bound cashflow reaches {weakest_lower_bound:.2f}, below policy cash buffer."
                ),
                current_value=round(weakest_lower_bound, 2),
                threshold_value=round(float(policy.minimum_cash_buffer), 2),
                delta_value=round(float(policy.minimum_cash_buffer) - weakest_lower_bound, 2),
                window_start_date=current_start_date,
                window_end_date=current_end_date,
            )
        )

    return alerts


def generate_lender_export_pack(
    db: Session,
    *,
    business_id: str,
    window_days: int = 30,
    history_days: int = 120,
    horizon_days: int = 90,
) -> LenderExportPackOut:
    profile = get_credit_profile_v2(db, business_id=business_id, window_days=window_days)
    forecast = get_cashflow_forecast(
        db,
        business_id=business_id,
        horizon_days=horizon_days,
        history_days=history_days,
        interval_days=30,
    )
    statements = _lender_statement_periods(db, business_id=business_id, months=6)

    return LenderExportPackOut(
        pack_id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc),
        window_days=window_days,
        horizon_days=horizon_days,
        profile=profile,
        forecast=forecast,
        statement_periods=statements,
        score_explanation=[item.rationale for item in profile.factors],
        recommendations=list(profile.recommendations),
        bundle_sections=[
            "credit_profile_v2",
            "cashflow_forecast",
            "statement_periods",
            "score_explanation",
            "recommendations",
        ],
    )


def build_credit_improvement_plan(
    db: Session,
    *,
    business_id: str,
    window_days: int = 30,
    target_score: int = 80,
) -> CreditImprovementPlanOut:
    profile = get_credit_profile_v2(db, business_id=business_id, window_days=window_days)
    desired_score = int(_clamp(float(target_score)))

    templates: dict[str, tuple[str, str, str]] = {
        "revenue_trend": (
            "Increase recurring sales momentum",
            "Launch retention and referral campaigns in the highest-performing channel for 2-4 weeks.",
            "Improve weekly net sales growth by at least 10%.",
        ),
        "profit_trend": (
            "Raise net cashflow trend",
            "Trim low-margin discounts and rebalance costs on top-selling SKUs.",
            "Increase weekly net cashflow by at least 8%.",
        ),
        "margin_quality": (
            "Protect gross and net margin",
            "Review pricing against costs and remove underpriced bundles.",
            "Lift margin ratio by at least 5 percentage points.",
        ),
        "expense_discipline": (
            "Reduce expense pressure",
            "Cap discretionary spend and enforce category budgets against campaign ROI.",
            "Reduce expense-to-sales ratio by at least 7 percentage points.",
        ),
        "refund_control": (
            "Lower refunds and leakage",
            "Audit fulfillment quality and remove recurring defect sources.",
            "Reduce refund transaction rate by at least 30%.",
        ),
        "cashflow_stability": (
            "Stabilize cashflow swings",
            "Stage inventory purchases and align promotions with expected cash inflows.",
            "Cut daily cashflow volatility by at least 20%.",
        ),
    }

    drafted_actions: list[CreditImprovementActionOut] = []
    for factor in sorted(profile.factors, key=lambda item: item.score):
        if factor.score >= 70:
            continue
        gap = max(0.0, min(100.0, desired_score) - factor.score)
        estimated_impact = round(min(15.0, max(2.0, gap * factor.weight + 1.5)), 2)
        title, description, measurable_target = templates.get(
            factor.key,
            (
                "Improve credit factor performance",
                "Apply targeted actions to strengthen this factor across the next reporting window.",
                "Increase factor score over the next 30 days.",
            ),
        )
        drafted_actions.append(
            CreditImprovementActionOut(
                priority=1,
                factor_key=factor.key,
                factor_label=factor.label,
                title=title,
                description=description,
                current_score=round(factor.score, 2),
                target_score=round(max(factor.score, min(100.0, desired_score)), 2),
                estimated_score_impact=estimated_impact,
                measurable_target=measurable_target,
            )
        )

    if not drafted_actions:
        drafted_actions.append(
            CreditImprovementActionOut(
                priority=1,
                factor_key="stability",
                factor_label="Overall Stability",
                title="Maintain current credit posture",
                description="Current trend is healthy. Maintain policy guardrails and monitor weekly.",
                current_score=float(profile.overall_score),
                target_score=float(max(profile.overall_score, desired_score)),
                estimated_score_impact=2.0,
                measurable_target="Sustain score and avoid guardrail breaches for the next 30 days.",
            )
        )

    ranked = sorted(drafted_actions, key=lambda item: item.estimated_score_impact, reverse=True)
    prioritized: list[CreditImprovementActionOut] = []
    for idx, action in enumerate(ranked, start=1):
        prioritized.append(action.model_copy(update={"priority": idx}))

    return CreditImprovementPlanOut(
        overall_score=profile.overall_score,
        target_score=desired_score,
        actions=prioritized,
        generated_at=datetime.now(timezone.utc),
    )


def get_finance_guardrail_evaluation(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str | None,
    window_days: int = 30,
    history_days: int = 90,
    horizon_days: int = 30,
    interval_days: int = 7,
) -> FinanceGuardrailEvaluationOut:
    policy = get_or_create_finance_guardrail_policy(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
    )
    alerts = evaluate_finance_guardrails(
        db,
        business_id=business_id,
        policy=policy,
        window_days=window_days,
        history_days=history_days,
        horizon_days=horizon_days,
        interval_days=interval_days,
    )
    return FinanceGuardrailEvaluationOut(
        policy=finance_guardrail_policy_out(policy),
        alerts=alerts,
        generated_at=datetime.now(timezone.utc),
    )


def _coerce_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _pct_change(current_value: float, previous_value: float) -> float:
    if abs(previous_value) < 1e-9:
        if abs(current_value) < 1e-9:
            return 0.0
        return 1.0
    return (current_value - previous_value) / abs(previous_value)


def _trend_from_delta(delta_pct: float, tolerance: float = 0.01) -> str:
    if delta_pct > tolerance:
        return "up"
    if delta_pct < -tolerance:
        return "down"
    return "flat"


def _linear_slope(values: list[float]) -> float:
    length = len(values)
    if length <= 1:
        return 0.0

    x_mean = (length - 1) / 2
    y_mean = fmean(values)
    denominator = sum((idx - x_mean) ** 2 for idx in range(length))
    if denominator <= 0:
        return 0.0
    numerator = sum((idx - x_mean) * (value - y_mean) for idx, value in enumerate(values))
    return numerator / denominator


def _volatility_ratio(values: list[float]) -> float:
    if not values:
        return 0.0
    volatility = pstdev(values) if len(values) > 1 else 0.0
    return volatility / max(abs(fmean(values)), 1.0)


def _historical_cashflow_series(
    db: Session,
    *,
    business_id: str,
    start_date: date,
    end_date: date,
) -> DailyCashflowSeries:
    sales_rows = db.execute(
        select(
            func.date(Sale.created_at),
            Sale.kind,
            func.coalesce(func.sum(Sale.total_amount), 0),
        )
        .where(
            Sale.business_id == business_id,
            func.date(Sale.created_at) >= start_date,
            func.date(Sale.created_at) <= end_date,
        )
        .group_by(func.date(Sale.created_at), Sale.kind)
    ).all()

    expense_rows = db.execute(
        select(
            func.date(Expense.created_at),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .where(
            Expense.business_id == business_id,
            func.date(Expense.created_at) >= start_date,
            func.date(Expense.created_at) <= end_date,
        )
        .group_by(func.date(Expense.created_at))
    ).all()

    inflow_by_day: dict[date, float] = {}
    refunds_by_day: dict[date, float] = {}
    for row_date, kind, amount in sales_rows:
        day = _coerce_date(row_date)
        amount_value = float(to_money(amount or 0))
        if str(kind).strip().lower() == "refund":
            refunds_by_day[day] = refunds_by_day.get(day, 0.0) + abs(amount_value)
        else:
            inflow_by_day[day] = inflow_by_day.get(day, 0.0) + max(amount_value, 0.0)

    expense_by_day: dict[date, float] = {}
    for row_date, amount in expense_rows:
        day = _coerce_date(row_date)
        expense_by_day[day] = expense_by_day.get(day, 0.0) + float(to_money(amount or 0))

    dates: list[date] = []
    inflows: list[float] = []
    outflows: list[float] = []
    nets: list[float] = []
    cursor = start_date
    while cursor <= end_date:
        inflow = inflow_by_day.get(cursor, 0.0)
        outflow = expense_by_day.get(cursor, 0.0) + refunds_by_day.get(cursor, 0.0)
        net = inflow - outflow

        dates.append(cursor)
        inflows.append(inflow)
        outflows.append(outflow)
        nets.append(net)
        cursor += timedelta(days=1)

    return DailyCashflowSeries(dates=dates, inflows=inflows, outflows=outflows, nets=nets)


def _window_financials(
    db: Session,
    *,
    business_id: str,
    start_date: date,
    end_date: date,
) -> WindowFinancials:
    sales_total = float(
        to_money(
            db.execute(
                select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                    Sale.business_id == business_id,
                    Sale.kind == "sale",
                    func.date(Sale.created_at) >= start_date,
                    func.date(Sale.created_at) <= end_date,
                )
            ).scalar_one()
            or 0
        )
    )
    refunds_total_raw = float(
        to_money(
            db.execute(
                select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                    Sale.business_id == business_id,
                    Sale.kind == "refund",
                    func.date(Sale.created_at) >= start_date,
                    func.date(Sale.created_at) <= end_date,
                )
            ).scalar_one()
            or 0
        )
    )
    net_sales = float(
        to_money(
            db.execute(
                select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                    Sale.business_id == business_id,
                    func.date(Sale.created_at) >= start_date,
                    func.date(Sale.created_at) <= end_date,
                )
            ).scalar_one()
            or 0
        )
    )
    expenses_total = float(
        to_money(
            db.execute(
                select(func.coalesce(func.sum(Expense.amount), 0)).where(
                    Expense.business_id == business_id,
                    func.date(Expense.created_at) >= start_date,
                    func.date(Expense.created_at) <= end_date,
                )
            ).scalar_one()
            or 0
        )
    )
    sale_count = int(
        db.execute(
            select(func.count(Sale.id)).where(
                Sale.business_id == business_id,
                Sale.kind == "sale",
                func.date(Sale.created_at) >= start_date,
                func.date(Sale.created_at) <= end_date,
            )
        ).scalar_one()
        or 0
    )
    refund_count = int(
        db.execute(
            select(func.count(Sale.id)).where(
                Sale.business_id == business_id,
                Sale.kind == "refund",
                func.date(Sale.created_at) >= start_date,
                func.date(Sale.created_at) <= end_date,
            )
        ).scalar_one()
        or 0
    )
    payment_methods_count = int(
        db.execute(
            select(func.count(func.distinct(Sale.payment_method))).where(
                Sale.business_id == business_id,
                Sale.kind == "sale",
                func.date(Sale.created_at) >= start_date,
                func.date(Sale.created_at) <= end_date,
            )
        ).scalar_one()
        or 0
    )
    series = _historical_cashflow_series(
        db,
        business_id=business_id,
        start_date=start_date,
        end_date=end_date,
    )
    return WindowFinancials(
        start_date=start_date,
        end_date=end_date,
        sales_total=sales_total,
        refunds_total_abs=abs(refunds_total_raw),
        net_sales=net_sales,
        expenses_total=expenses_total,
        sale_count=sale_count,
        refund_count=refund_count,
        payment_methods_count=payment_methods_count,
        daily_net_values=series.nets,
    )


def _build_credit_factors(
    *,
    current: WindowFinancials,
    previous: WindowFinancials,
) -> list[CreditScoreFactorOut]:
    current_profit = current.net_sales - current.expenses_total
    previous_profit = previous.net_sales - previous.expenses_total
    current_margin = current_profit / max(current.net_sales, 1.0) if current.net_sales > 0 else -1.0
    previous_margin = previous_profit / max(previous.net_sales, 1.0) if previous.net_sales > 0 else -1.0
    current_expense_ratio = current.expenses_total / max(current.net_sales, 1.0) if current.net_sales > 0 else 1.0
    previous_expense_ratio = (
        previous.expenses_total / max(previous.net_sales, 1.0) if previous.net_sales > 0 else 1.0
    )
    current_refund_rate = current.refund_count / max(current.sale_count, 1)
    previous_refund_rate = previous.refund_count / max(previous.sale_count, 1)
    current_volatility = _volatility_ratio(current.daily_net_values)
    previous_volatility = _volatility_ratio(previous.daily_net_values)

    revenue_delta_pct = _pct_change(current.net_sales, previous.net_sales)
    profit_delta_pct = _pct_change(current_profit, previous_profit)
    margin_delta = current_margin - previous_margin
    expense_ratio_delta = previous_expense_ratio - current_expense_ratio
    refund_delta = previous_refund_rate - current_refund_rate
    volatility_delta = previous_volatility - current_volatility

    revenue_score = _clamp(50 + revenue_delta_pct * 100)
    profit_score = _clamp(50 + profit_delta_pct * 100)
    margin_score = _clamp((current_margin + 0.1) * 200 + margin_delta * 60)
    expense_score = _clamp((0.85 - current_expense_ratio) * 120 + expense_ratio_delta * 40)
    refund_score = _clamp(((0.15 - current_refund_rate) / 0.15) * 100 + refund_delta * 80)
    stability_score = _clamp(100 - current_volatility * 100 + volatility_delta * 40)

    factors = [
        CreditScoreFactorOut(
            key="revenue_trend",
            label="Revenue Momentum",
            score=round(revenue_score, 2),
            weight=0.20,
            current_value=round(current.net_sales, 2),
            previous_value=round(previous.net_sales, 2),
            delta_pct=round(revenue_delta_pct, 4),
            trend=_trend_from_delta(revenue_delta_pct),
            rationale=(
                f"Net sales moved from {previous.net_sales:.2f} to {current.net_sales:.2f} across consecutive windows."
            ),
        ),
        CreditScoreFactorOut(
            key="profit_trend",
            label="Profit Trend",
            score=round(profit_score, 2),
            weight=0.20,
            current_value=round(current_profit, 2),
            previous_value=round(previous_profit, 2),
            delta_pct=round(profit_delta_pct, 4),
            trend=_trend_from_delta(profit_delta_pct),
            rationale=(
                f"Net cashflow trend shifted from {previous_profit:.2f} to {current_profit:.2f}; trend quality drives credit confidence."
            ),
        ),
        CreditScoreFactorOut(
            key="margin_quality",
            label="Margin Quality",
            score=round(margin_score, 2),
            weight=0.20,
            current_value=round(current_margin, 4),
            previous_value=round(previous_margin, 4),
            delta_pct=round(_pct_change(current_margin, previous_margin), 4),
            trend=_trend_from_delta(margin_delta),
            rationale=(
                f"Margin is {current_margin * 100:.1f}% vs {previous_margin * 100:.1f}% in the prior window."
            ),
        ),
        CreditScoreFactorOut(
            key="expense_discipline",
            label="Expense Discipline",
            score=round(expense_score, 2),
            weight=0.15,
            current_value=round(current_expense_ratio, 4),
            previous_value=round(previous_expense_ratio, 4),
            delta_pct=round(_pct_change(current_expense_ratio, previous_expense_ratio), 4),
            trend=_trend_from_delta(expense_ratio_delta),
            rationale=(
                f"Expense-to-sales ratio is {current_expense_ratio * 100:.1f}% compared with {previous_expense_ratio * 100:.1f}% previously."
            ),
        ),
        CreditScoreFactorOut(
            key="refund_control",
            label="Refund Control",
            score=round(refund_score, 2),
            weight=0.15,
            current_value=round(current_refund_rate, 4),
            previous_value=round(previous_refund_rate, 4),
            delta_pct=round(_pct_change(current_refund_rate, previous_refund_rate), 4),
            trend=_trend_from_delta(refund_delta),
            rationale=(
                f"Refund transaction rate is {current_refund_rate * 100:.1f}% versus {previous_refund_rate * 100:.1f}% in the prior window."
            ),
        ),
        CreditScoreFactorOut(
            key="cashflow_stability",
            label="Cashflow Stability",
            score=round(stability_score, 2),
            weight=0.10,
            current_value=round(current_volatility, 4),
            previous_value=round(previous_volatility, 4),
            delta_pct=round(_pct_change(current_volatility, previous_volatility), 4),
            trend=_trend_from_delta(volatility_delta),
            rationale=(
                f"Daily net-cashflow volatility index is {current_volatility:.2f}, against {previous_volatility:.2f} in the prior window."
            ),
        ),
    ]
    return factors


def _factor_recommendations(factors: list[CreditScoreFactorOut]) -> list[str]:
    ranked = sorted(factors, key=lambda item: item.score)
    recommendations: list[str] = []
    for factor in ranked:
        if factor.score >= 60:
            continue
        if factor.key == "revenue_trend":
            recommendations.append("Increase repeat-order campaigns and improve conversion in your best-performing sales channel.")
        elif factor.key == "profit_trend":
            recommendations.append("Protect weekly net cashflow by raising low-margin prices and reducing avoidable discounts.")
        elif factor.key == "margin_quality":
            recommendations.append("Review SKU-level pricing against cost to restore margin above your current baseline.")
        elif factor.key == "expense_discipline":
            recommendations.append("Set a spending cap per week and tie discretionary expenses to active revenue campaigns.")
        elif factor.key == "refund_control":
            recommendations.append("Investigate top refund causes and tighten quality checks for frequently returned SKUs.")
        elif factor.key == "cashflow_stability":
            recommendations.append("Smooth cashflow swings by balancing inventory purchases and planned campaign timing.")
        if len(recommendations) >= 3:
            break

    if not recommendations:
        recommendations.append("Credit trend is stable; maintain current operating discipline and monitor weekly.")
    return recommendations


def _scenario_outcome(
    *,
    label: str,
    intervals: list[CashflowForecastIntervalOut],
) -> CreditScenarioOutcomeOut:
    projected_revenue = round(sum(interval.projected_inflow for interval in intervals), 2)
    projected_expenses = round(sum(interval.projected_outflow for interval in intervals), 2)
    projected_net_cashflow = round(projected_revenue - projected_expenses, 2)
    projected_margin_pct = round(
        0.0 if projected_revenue <= 0 else (projected_net_cashflow / projected_revenue) * 100,
        2,
    )
    return CreditScenarioOutcomeOut(
        label=label,
        projected_revenue=projected_revenue,
        projected_expenses=projected_expenses,
        projected_net_cashflow=projected_net_cashflow,
        projected_margin_pct=projected_margin_pct,
        intervals=intervals,
    )


def lender_statement_periods(
    db: Session,
    *,
    business_id: str,
    months: int = 6,
) -> list[LenderPackStatementPeriodOut]:
    return _lender_statement_periods(db, business_id=business_id, months=months)


def finance_guardrail_policy_out(policy: FinanceGuardrailPolicy) -> FinanceGuardrailPolicyOut:
    return FinanceGuardrailPolicyOut(
        id=policy.id,
        enabled=bool(policy.enabled),
        margin_floor_ratio=float(policy.margin_floor_ratio),
        margin_drop_threshold=float(policy.margin_drop_threshold),
        expense_growth_threshold=float(policy.expense_growth_threshold),
        minimum_cash_buffer=float(policy.minimum_cash_buffer),
        updated_by_user_id=policy.updated_by_user_id,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _lender_statement_periods(
    db: Session,
    *,
    business_id: str,
    months: int = 6,
) -> list[LenderPackStatementPeriodOut]:
    periods: list[LenderPackStatementPeriodOut] = []
    first_of_this_month = date.today().replace(day=1)
    for offset in range(max(1, months)):
        period_end = first_of_this_month - timedelta(days=1)
        for _ in range(offset):
            period_end = period_end.replace(day=1) - timedelta(days=1)
        period_start = period_end.replace(day=1)

        net_sales = float(
            to_money(
                db.execute(
                    select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                        Sale.business_id == business_id,
                        func.date(Sale.created_at) >= period_start,
                        func.date(Sale.created_at) <= period_end,
                    )
                ).scalar_one()
                or 0
            )
        )
        expenses_total = float(
            to_money(
                db.execute(
                    select(func.coalesce(func.sum(Expense.amount), 0)).where(
                        Expense.business_id == business_id,
                        func.date(Expense.created_at) >= period_start,
                        func.date(Expense.created_at) <= period_end,
                    )
                ).scalar_one()
                or 0
            )
        )
        periods.append(
            LenderPackStatementPeriodOut(
                period_label=period_start.strftime("%Y-%m"),
                period_start_date=period_start,
                period_end_date=period_end,
                net_sales=round(net_sales, 2),
                expenses_total=round(expenses_total, 2),
                net_cashflow=round(net_sales - expenses_total, 2),
            )
        )
    periods.reverse()
    return periods
