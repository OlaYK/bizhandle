import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.money import to_money
from app.models.ai_copilot import (
    AIFeatureSnapshot,
    AIGeneratedInsight,
    AIGovernanceTrace,
    AIPrescriptiveAction,
    AIRiskAlertConfig,
    AIRiskAlertEvent,
)
from app.models.ai_insight import AIInsightLog
from app.models.analytics import AnalyticsDailyMetric
from app.models.campaign import Campaign
from app.models.expense import Expense
from app.models.inventory import InventoryLedger
from app.models.order import Order
from app.models.product import ProductVariant
from app.models.sales import Sale

PAID_ORDER_STATUSES = {"paid", "processing", "fulfilled"}


@dataclass
class PermittedBusinessSnapshot:
    sales_total: float
    sales_count: int
    average_sale_value: float
    expense_total: float
    expense_count: int
    profit_simple: float
    top_sales_channel: str | None
    top_payment_method: str | None
    orders_count_window: int
    paid_orders_count_window: int
    refund_rate_window: float
    stockout_events_window: int
    campaigns_sent_window: int
    campaigns_failed_window: int
    repeat_customers_window: int
    net_revenue_window: float
    expenses_window: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sales_total": self.sales_total,
            "sales_count": self.sales_count,
            "average_sale_value": self.average_sale_value,
            "expense_total": self.expense_total,
            "expense_count": self.expense_count,
            "profit_simple": self.profit_simple,
            "top_sales_channel": self.top_sales_channel,
            "top_payment_method": self.top_payment_method,
            "orders_count_window": self.orders_count_window,
            "paid_orders_count_window": self.paid_orders_count_window,
            "refund_rate_window": self.refund_rate_window,
            "stockout_events_window": self.stockout_events_window,
            "campaigns_sent_window": self.campaigns_sent_window,
            "campaigns_failed_window": self.campaigns_failed_window,
            "repeat_customers_window": self.repeat_customers_window,
            "net_revenue_window": self.net_revenue_window,
            "expenses_window": self.expenses_window,
        }


@dataclass
class FeatureSnapshotMetrics:
    window_start_date: date
    window_end_date: date
    orders_count: int
    paid_orders_count: int
    gross_revenue: Decimal
    refunds_count: int
    refunds_amount: Decimal
    net_revenue: Decimal
    expenses_total: Decimal
    refund_rate: float
    stockout_events_count: int
    campaigns_sent_count: int
    campaigns_failed_count: int
    repeat_customers_count: int
    metadata_json: dict[str, Any] | None


@dataclass
class InsightCandidate:
    insight_type: str
    severity: str
    title: str
    summary: str
    confidence_score: float
    context_json: dict[str, Any]
    action_type: str
    action_title: str
    action_description: str
    action_payload: dict[str, Any] | None


@dataclass
class AIProviderResult:
    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None


@dataclass
class AIServiceResult:
    response: str
    log: AIInsightLog


@dataclass
class CuratedMetric:
    key: str
    value: float | str
    source: str


@dataclass
class AnalyticsAssistantResult:
    answer: str
    metrics: list[CuratedMetric]
    trace: AIGovernanceTrace


@dataclass
class RiskAlertEvaluation:
    snapshot: AIFeatureSnapshot
    events: list[AIRiskAlertEvent]


class AIProvider(Protocol):
    provider: str
    model: str

    def complete(self, *, system_prompt: str, user_prompt: str) -> AIProviderResult:
        ...


class StubAIProvider:
    provider = f"{settings.ai_vendor}:{settings.ai_provider}"

    def __init__(self, model: str):
        self.model = model

    def complete(self, *, system_prompt: str, user_prompt: str) -> AIProviderResult:
        task = self._extract_value(user_prompt, "TASK")
        context = self._extract_context(user_prompt)
        if task == "question_answer":
            question = self._extract_value(user_prompt, "QUESTION")
            text = self._answer_question(context, question)
        else:
            text = self._generate_daily_insight(context)

        prompt_tokens = self._estimate_tokens(system_prompt + "\n" + user_prompt)
        completion_tokens = self._estimate_tokens(text)
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost_usd = round((total_tokens / 1000) * settings.ai_cost_per_1k_tokens_usd, 6)
        return AIProviderResult(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    @staticmethod
    def _extract_value(prompt: str, key: str) -> str:
        match = re.search(rf"{key}:\s*(.+)", prompt)
        if not match:
            return ""
        return match.group(1).strip()

    @staticmethod
    def _extract_context(prompt: str) -> dict[str, Any]:
        match = re.search(r"ALLOWED_FIELDS_JSON:\s*(\{.*?\})", prompt, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _generate_daily_insight(context: dict[str, Any]) -> str:
        sales_total = float(context.get("sales_total", 0))
        expense_total = float(context.get("expense_total", 0))
        profit_simple = float(context.get("profit_simple", 0))
        top_channel = context.get("top_sales_channel") or "unknown"
        top_payment = context.get("top_payment_method") or "unknown"
        refund_rate = float(context.get("refund_rate_window", 0))
        stockout_risk = int(context.get("stockout_events_window", 0))

        if sales_total <= 0:
            return (
                "- Record at least 3 sales this week to establish a baseline.\n"
                "- Track expenses by category daily to identify avoidable spend.\n"
                "- Keep payment-method and channel data consistent from today."
            )

        margin_pct = 0.0 if sales_total == 0 else (profit_simple / sales_total) * 100
        stock_line = (
            f"- {stockout_risk} variants are at/under threshold; trigger immediate restock planning."
            if stockout_risk > 0
            else "- Stock position is stable; keep reorder discipline for fast-moving items."
        )
        return (
            f"- Profit is {profit_simple:.2f} on sales of {sales_total:.2f}; target margin is >20% "
            f"(current {margin_pct:.1f}%).\n"
            f"- Refund rate in the active window is {refund_rate * 100:.1f}%; top channel is {top_channel}, "
            f"top payment method is {top_payment}.\n"
            f"{stock_line} (expenses currently {expense_total:.2f})."
        )

    @staticmethod
    def _answer_question(context: dict[str, Any], question: str) -> str:
        q = question.lower()
        sales_total = float(context.get("sales_total", 0))
        expense_total = float(context.get("expense_total", 0))
        profit_simple = float(context.get("profit_simple", 0))
        avg_sale = float(context.get("average_sale_value", 0))
        top_channel = context.get("top_sales_channel") or "unknown"
        top_payment = context.get("top_payment_method") or "unknown"
        refund_rate = float(context.get("refund_rate_window", 0))
        stockout_risk = int(context.get("stockout_events_window", 0))
        repeat_customers = int(context.get("repeat_customers_window", 0))
        campaigns_failed = int(context.get("campaigns_failed_window", 0))
        campaigns_sent = int(context.get("campaigns_sent_window", 0))
        orders_count = int(context.get("orders_count_window", 0))

        if "profit" in q:
            return f"Simple profit is {profit_simple:.2f} (sales {sales_total:.2f} minus expenses {expense_total:.2f})."
        if "expense" in q or "cost" in q:
            return f"Total expenses are {expense_total:.2f}. Compare this against sales {sales_total:.2f} to control burn."
        if "sales" in q or "revenue" in q:
            return f"Total sales are {sales_total:.2f}, with average sale value {avg_sale:.2f}."
        if "channel" in q:
            return f"Top sales channel in available data is {top_channel}."
        if "payment" in q:
            return f"Most-used payment method in available data is {top_payment}."
        if "refund" in q:
            return f"Refund rate in the current window is {refund_rate * 100:.1f}%."
        if "stock" in q or "inventory" in q:
            return f"{stockout_risk} variants are at or below threshold in the active window."
        if "repeat" in q or "retention" in q:
            return f"Repeat customers in the current window: {repeat_customers} out of {orders_count} total orders."
        if "campaign" in q or "message" in q:
            return f"Campaign outcomes in window: {campaigns_sent} sent and {campaigns_failed} failed."
        return (
            "I can answer from permitted fields only: sales_total, sales_count, average_sale_value, "
            "expense_total, expense_count, profit_simple, top_sales_channel, top_payment_method, "
            "orders_count_window, paid_orders_count_window, refund_rate_window, stockout_events_window, "
            "campaigns_sent_window, campaigns_failed_window, repeat_customers_window, net_revenue_window, expenses_window."
        )


class OpenAIProvider:
    provider = f"{settings.ai_vendor}:openai"

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ValueError("openai dependency is not installed") from exc

        client_kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(**client_kwargs)
        self.model = model

    def complete(self, *, system_prompt: str, user_prompt: str) -> AIProviderResult:
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.ai_temperature,
        )

        text = ""
        if completion.choices and completion.choices[0].message:
            text = completion.choices[0].message.content or ""

        usage = completion.usage
        prompt_tokens = usage.prompt_tokens if usage else None
        completion_tokens = usage.completion_tokens if usage else None
        total_tokens = usage.total_tokens if usage else None
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        estimated_cost_usd = None
        if total_tokens is not None:
            estimated_cost_usd = round((total_tokens / 1000) * settings.ai_cost_per_1k_tokens_usd, 6)

        return AIProviderResult(
            text=text.strip(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )

def generate_insight(db: Session, business_id: str) -> AIServiceResult:
    snapshot = _load_permitted_snapshot(db, business_id)
    context = snapshot.to_dict()
    provider = _get_provider()

    system_prompt = _insight_system_prompt()
    user_prompt = _daily_insight_user_prompt(context)
    completion = provider.complete(system_prompt=system_prompt, user_prompt=user_prompt)
    log = _build_log(
        business_id=business_id,
        insight_type="daily_insight",
        prompt=_compose_prompt(system_prompt, user_prompt),
        response=completion.text,
        provider=provider.provider,
        model=provider.model,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
        estimated_cost_usd=completion.estimated_cost_usd,
        metadata_json={"allowed_fields": list(context.keys()), "context": context},
    )
    return AIServiceResult(response=completion.text, log=log)


def answer_business_question(db: Session, business_id: str, question: str) -> AIServiceResult:
    snapshot = _load_permitted_snapshot(db, business_id)
    context = snapshot.to_dict()
    provider = _get_provider()

    clean_question = question.strip()
    if len(clean_question) > settings.ai_max_question_chars:
        clean_question = clean_question[: settings.ai_max_question_chars]

    system_prompt = _ask_system_prompt()
    user_prompt = _ask_user_prompt(context, clean_question)
    completion = provider.complete(system_prompt=system_prompt, user_prompt=user_prompt)
    log = _build_log(
        business_id=business_id,
        insight_type="question_answer",
        prompt=_compose_prompt(system_prompt, user_prompt),
        response=completion.text,
        provider=provider.provider,
        model=provider.model,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
        estimated_cost_usd=completion.estimated_cost_usd,
        metadata_json={
            "allowed_fields": list(context.keys()),
            "context": context,
            "question": clean_question,
        },
    )
    return AIServiceResult(response=completion.text, log=log)


def latest_feature_snapshot(db: Session, business_id: str) -> AIFeatureSnapshot | None:
    return db.execute(
        select(AIFeatureSnapshot)
        .where(AIFeatureSnapshot.business_id == business_id)
        .order_by(AIFeatureSnapshot.window_end_date.desc(), AIFeatureSnapshot.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def refresh_feature_snapshot(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str | None,
    window_days: int = 30,
) -> AIFeatureSnapshot:
    window_start_date, window_end_date = _resolve_window(window_days)
    metrics = _compute_feature_snapshot_metrics(
        db,
        business_id=business_id,
        window_start_date=window_start_date,
        window_end_date=window_end_date,
    )

    snapshot = db.execute(
        select(AIFeatureSnapshot).where(
            AIFeatureSnapshot.business_id == business_id,
            AIFeatureSnapshot.window_start_date == window_start_date,
            AIFeatureSnapshot.window_end_date == window_end_date,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        snapshot = AIFeatureSnapshot(
            id=str(uuid.uuid4()),
            business_id=business_id,
            created_by_user_id=actor_user_id,
            window_start_date=window_start_date,
            window_end_date=window_end_date,
        )
        db.add(snapshot)

    snapshot.orders_count = metrics.orders_count
    snapshot.paid_orders_count = metrics.paid_orders_count
    snapshot.gross_revenue = to_money(metrics.gross_revenue)
    snapshot.refunds_count = metrics.refunds_count
    snapshot.refunds_amount = to_money(metrics.refunds_amount)
    snapshot.net_revenue = to_money(metrics.net_revenue)
    snapshot.expenses_total = to_money(metrics.expenses_total)
    snapshot.refund_rate = float(metrics.refund_rate)
    snapshot.stockout_events_count = metrics.stockout_events_count
    snapshot.campaigns_sent_count = metrics.campaigns_sent_count
    snapshot.campaigns_failed_count = metrics.campaigns_failed_count
    snapshot.repeat_customers_count = metrics.repeat_customers_count
    snapshot.metadata_json = metrics.metadata_json
    return snapshot


def generate_v2_insights(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str,
    window_days: int = 30,
) -> tuple[AIFeatureSnapshot, list[AIGeneratedInsight], list[AIPrescriptiveAction]]:
    snapshot = refresh_feature_snapshot(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        window_days=window_days,
    )

    candidates = _build_insight_candidates(snapshot)
    insights: list[AIGeneratedInsight] = []
    actions: list[AIPrescriptiveAction] = []
    for candidate in candidates:
        insight = AIGeneratedInsight(
            id=str(uuid.uuid4()),
            business_id=business_id,
            feature_snapshot_id=snapshot.id,
            insight_type=candidate.insight_type,
            severity=candidate.severity,
            title=candidate.title,
            summary=candidate.summary,
            confidence_score=float(candidate.confidence_score),
            status="open",
            context_json=candidate.context_json,
        )
        db.add(insight)
        db.flush()
        insights.append(insight)

        action = AIPrescriptiveAction(
            id=str(uuid.uuid4()),
            business_id=business_id,
            insight_id=insight.id,
            action_type=candidate.action_type,
            title=candidate.action_title,
            description=candidate.action_description,
            payload_json=candidate.action_payload,
            status="proposed",
            decision_note=None,
        )
        db.add(action)
        actions.append(action)

    return snapshot, insights, actions


def create_governance_trace(
    db: Session,
    *,
    business_id: str,
    trace_type: str,
    prompt: str,
    context_json: dict[str, Any] | None,
    output_json: dict[str, Any] | None,
    actor_user_id: str | None = None,
    feature_snapshot_id: str | None = None,
) -> AIGovernanceTrace:
    trace = AIGovernanceTrace(
        id=str(uuid.uuid4()),
        business_id=business_id,
        trace_type=trace_type,
        actor_user_id=actor_user_id,
        feature_snapshot_id=feature_snapshot_id,
        prompt=prompt,
        context_json=context_json,
        output_json=output_json,
    )
    db.add(trace)
    return trace


def get_or_create_risk_alert_config(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str | None,
) -> AIRiskAlertConfig:
    config = db.execute(
        select(AIRiskAlertConfig).where(AIRiskAlertConfig.business_id == business_id)
    ).scalar_one_or_none()
    if config is None:
        config = AIRiskAlertConfig(
            id=str(uuid.uuid4()),
            business_id=business_id,
            enabled=True,
            refund_rate_threshold=0.1,
            stockout_threshold=3,
            cashflow_margin_threshold=0.15,
            channels_json=["in_app"],
            updated_by_user_id=actor_user_id,
        )
        db.add(config)
        db.flush()
    return config


def update_risk_alert_config(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str,
    enabled: bool,
    refund_rate_threshold: float,
    stockout_threshold: int,
    cashflow_margin_threshold: float,
    channels: list[str],
) -> AIRiskAlertConfig:
    config = get_or_create_risk_alert_config(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
    )
    config.enabled = bool(enabled)
    config.refund_rate_threshold = float(refund_rate_threshold)
    config.stockout_threshold = int(stockout_threshold)
    config.cashflow_margin_threshold = float(cashflow_margin_threshold)
    config.channels_json = _normalize_channels(channels)
    config.updated_by_user_id = actor_user_id
    return config


def evaluate_risk_alerts(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str | None,
    window_days: int = 30,
) -> RiskAlertEvaluation:
    config = get_or_create_risk_alert_config(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
    )
    snapshot = refresh_feature_snapshot(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        window_days=window_days,
    )
    if not config.enabled:
        return RiskAlertEvaluation(snapshot=snapshot, events=[])

    events: list[AIRiskAlertEvent] = []
    channels = _normalize_channels(config.channels_json)
    refund_rate = float(snapshot.refund_rate or 0)
    stockout_count = int(snapshot.stockout_events_count or 0)
    net_revenue = float(to_money(snapshot.net_revenue or 0))
    expenses_total = float(to_money(snapshot.expenses_total or 0))
    margin_rate = -1.0 if net_revenue <= 0 else (net_revenue - expenses_total) / max(net_revenue, 1)

    if refund_rate >= float(config.refund_rate_threshold):
        event = AIRiskAlertEvent(
            id=str(uuid.uuid4()),
            business_id=business_id,
            config_id=config.id,
            alert_type="refund_spike",
            severity="high" if refund_rate >= max(0.2, config.refund_rate_threshold * 1.5) else "medium",
            status="triggered",
            message=f"Refund rate reached {refund_rate * 100:.1f}% in the active window.",
            triggered_value=refund_rate,
            threshold_value=float(config.refund_rate_threshold),
            channels_json=channels,
            context_json={
                "window_start_date": snapshot.window_start_date.isoformat(),
                "window_end_date": snapshot.window_end_date.isoformat(),
                "refunds_count": int(snapshot.refunds_count or 0),
            },
        )
        db.add(event)
        events.append(event)

    if stockout_count >= int(config.stockout_threshold):
        event = AIRiskAlertEvent(
            id=str(uuid.uuid4()),
            business_id=business_id,
            config_id=config.id,
            alert_type="stockout_risk",
            severity="high" if stockout_count >= max(5, int(config.stockout_threshold) * 2) else "medium",
            status="triggered",
            message=f"Stockout risk detected on {stockout_count} variants.",
            triggered_value=float(stockout_count),
            threshold_value=float(config.stockout_threshold),
            channels_json=channels,
            context_json={
                "window_start_date": snapshot.window_start_date.isoformat(),
                "window_end_date": snapshot.window_end_date.isoformat(),
            },
        )
        db.add(event)
        events.append(event)

    if margin_rate <= float(config.cashflow_margin_threshold):
        event = AIRiskAlertEvent(
            id=str(uuid.uuid4()),
            business_id=business_id,
            config_id=config.id,
            alert_type="cashflow_drop",
            severity="high" if margin_rate <= 0 else "medium",
            status="triggered",
            message=f"Cashflow margin is {margin_rate * 100:.1f}% (below threshold).",
            triggered_value=margin_rate,
            threshold_value=float(config.cashflow_margin_threshold),
            channels_json=channels,
            context_json={
                "net_revenue": net_revenue,
                "expenses_total": expenses_total,
                "window_start_date": snapshot.window_start_date.isoformat(),
                "window_end_date": snapshot.window_end_date.isoformat(),
            },
        )
        db.add(event)
        events.append(event)

    return RiskAlertEvaluation(snapshot=snapshot, events=events)


def answer_analytics_assistant_query(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str,
    question: str,
    window_days: int = 30,
) -> AnalyticsAssistantResult:
    clean_question = question.strip()
    if len(clean_question) > settings.ai_max_question_chars:
        clean_question = clean_question[: settings.ai_max_question_chars]

    snapshot = refresh_feature_snapshot(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        window_days=window_days,
    )
    metrics = _curated_metrics(db, business_id=business_id, snapshot=snapshot)
    answer = _answer_curated_metrics_question(clean_question, metrics)
    trace = create_governance_trace(
        db,
        business_id=business_id,
        trace_type="analytics_assistant.query",
        actor_user_id=actor_user_id,
        feature_snapshot_id=snapshot.id,
        prompt=clean_question,
        context_json={
            "window_days": window_days,
            "window_start_date": snapshot.window_start_date.isoformat(),
            "window_end_date": snapshot.window_end_date.isoformat(),
            "metrics": {item.key: item.value for item in metrics},
        },
        output_json={"answer": answer},
    )
    return AnalyticsAssistantResult(answer=answer, metrics=metrics, trace=trace)

def _resolve_window(window_days: int) -> tuple[date, date]:
    normalized_window = max(7, min(int(window_days), 120))
    window_end_date = date.today()
    window_start_date = window_end_date - timedelta(days=normalized_window - 1)
    return window_start_date, window_end_date


def _compute_feature_snapshot_metrics(
    db: Session,
    *,
    business_id: str,
    window_start_date: date,
    window_end_date: date,
) -> FeatureSnapshotMetrics:
    order_filters = (
        Order.business_id == business_id,
        func.date(Order.created_at) >= window_start_date,
        func.date(Order.created_at) <= window_end_date,
    )
    orders_count = int(db.execute(select(func.count(Order.id)).where(*order_filters)).scalar_one() or 0)
    paid_orders_count = int(
        db.execute(
            select(func.count(Order.id)).where(
                *order_filters,
                Order.status.in_(list(PAID_ORDER_STATUSES)),
            )
        ).scalar_one()
        or 0
    )
    gross_revenue = to_money(
        db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                *order_filters,
                Order.status.in_(list(PAID_ORDER_STATUSES)),
            )
        ).scalar_one()
        or 0
    )

    sale_filters = (
        Sale.business_id == business_id,
        func.date(Sale.created_at) >= window_start_date,
        func.date(Sale.created_at) <= window_end_date,
    )
    refunds_count = int(
        db.execute(select(func.count(Sale.id)).where(*sale_filters, Sale.kind == "refund")).scalar_one() or 0
    )
    raw_refunds_amount = to_money(
        db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(*sale_filters, Sale.kind == "refund")
        ).scalar_one()
        or 0
    )
    refunds_amount = to_money(abs(raw_refunds_amount))
    net_revenue = to_money(gross_revenue - refunds_amount)

    expenses_total = to_money(
        db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.business_id == business_id,
                func.date(Expense.created_at) >= window_start_date,
                func.date(Expense.created_at) <= window_end_date,
            )
        ).scalar_one()
        or 0
    )
    refund_rate = 0.0 if orders_count <= 0 else min(1.0, refunds_count / max(orders_count, 1))

    stock_rows = db.execute(
        select(
            ProductVariant.id,
            ProductVariant.reorder_level,
            func.coalesce(func.sum(InventoryLedger.qty_delta), 0),
        )
        .outerjoin(InventoryLedger, InventoryLedger.variant_id == ProductVariant.id)
        .where(ProductVariant.business_id == business_id)
        .group_by(ProductVariant.id, ProductVariant.reorder_level)
    ).all()
    stockout_events_count = 0
    for _variant_id, reorder_level, current_qty in stock_rows:
        if int(current_qty or 0) <= int(reorder_level or 0):
            stockout_events_count += 1

    campaign_window_filters = (
        Campaign.business_id == business_id,
        func.date(Campaign.created_at) >= window_start_date,
        func.date(Campaign.created_at) <= window_end_date,
    )
    campaigns_sent_count = int(
        db.execute(
            select(func.coalesce(func.sum(Campaign.sent_count), 0)).where(*campaign_window_filters)
        ).scalar_one()
        or 0
    )
    campaigns_failed_count = int(
        db.execute(
            select(func.coalesce(func.sum(Campaign.failed_count), 0)).where(*campaign_window_filters)
        ).scalar_one()
        or 0
    )

    repeat_rows = db.execute(
        select(Order.customer_id, func.count(Order.id))
        .where(
            *order_filters,
            Order.customer_id.is_not(None),
        )
        .group_by(Order.customer_id)
    ).all()
    repeat_customers_count = sum(1 for _customer_id, count in repeat_rows if int(count or 0) >= 2)

    metadata_json = {
        "window_days": (window_end_date - window_start_date).days + 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return FeatureSnapshotMetrics(
        window_start_date=window_start_date,
        window_end_date=window_end_date,
        orders_count=orders_count,
        paid_orders_count=paid_orders_count,
        gross_revenue=gross_revenue,
        refunds_count=refunds_count,
        refunds_amount=refunds_amount,
        net_revenue=net_revenue,
        expenses_total=expenses_total,
        refund_rate=round(refund_rate, 4),
        stockout_events_count=stockout_events_count,
        campaigns_sent_count=campaigns_sent_count,
        campaigns_failed_count=campaigns_failed_count,
        repeat_customers_count=repeat_customers_count,
        metadata_json=metadata_json,
    )


def _build_insight_candidates(snapshot: AIFeatureSnapshot) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []
    orders_count = int(snapshot.orders_count or 0)
    paid_orders_count = int(snapshot.paid_orders_count or 0)
    refunds_count = int(snapshot.refunds_count or 0)
    refund_rate = float(snapshot.refund_rate or 0)
    stockout_count = int(snapshot.stockout_events_count or 0)
    campaigns_sent = int(snapshot.campaigns_sent_count or 0)
    campaigns_failed = int(snapshot.campaigns_failed_count or 0)
    repeat_customers = int(snapshot.repeat_customers_count or 0)
    net_revenue = float(to_money(snapshot.net_revenue or 0))
    expenses_total = float(to_money(snapshot.expenses_total or 0))
    margin_rate = 0.0 if net_revenue <= 0 else (net_revenue - expenses_total) / max(net_revenue, 1)
    paid_ratio = 0.0 if orders_count <= 0 else paid_orders_count / max(orders_count, 1)
    repeat_ratio = 0.0 if orders_count <= 0 else repeat_customers / max(orders_count, 1)

    if refund_rate >= 0.12 and refunds_count >= 2:
        candidates.append(
            InsightCandidate(
                insight_type="anomaly",
                severity="high",
                title="Refund pressure is above healthy threshold",
                summary=(
                    f"Refund rate is {refund_rate * 100:.1f}% with {refunds_count} refunds in the active window. "
                    "Investigate SKU quality issues and order fulfillment accuracy."
                ),
                confidence_score=0.91,
                context_json={"refund_rate": refund_rate, "refunds_count": refunds_count},
                action_type="refund_diagnostic",
                action_title="Run refund root-cause drilldown",
                action_description=(
                    "Review top refunded SKUs, inspect return reasons, and pause campaign traffic to weak items until fixed."
                ),
                action_payload={
                    "target": "refunds",
                    "threshold": 0.12,
                    "window_end_date": snapshot.window_end_date.isoformat(),
                },
            )
        )

    if stockout_count > 0:
        candidates.append(
            InsightCandidate(
                insight_type="urgency",
                severity="high" if stockout_count >= 3 else "medium",
                title="Stockout risk detected in active catalog",
                summary=(
                    f"{stockout_count} variants are at or below reorder threshold. "
                    "Immediate replenishment can prevent avoidable lost sales."
                ),
                confidence_score=0.88,
                context_json={"stockout_events_count": stockout_count},
                action_type="restock_plan",
                action_title="Create replenishment batch",
                action_description=(
                    "Prioritize fast-moving variants with low stock and generate a restock purchase plan for this week."
                ),
                action_payload={"target": "inventory", "priority": "high"},
            )
        )

    if campaigns_sent >= 10 and campaigns_failed > max(2, int(campaigns_sent * 0.2)):
        candidates.append(
            InsightCandidate(
                insight_type="anomaly",
                severity="medium",
                title="Campaign delivery quality has degraded",
                summary=(
                    f"Campaign failures are {campaigns_failed} against {campaigns_sent} sent messages. "
                    "Connector configuration or audience quality likely needs remediation."
                ),
                confidence_score=0.84,
                context_json={"campaigns_sent": campaigns_sent, "campaigns_failed": campaigns_failed},
                action_type="campaign_quality_audit",
                action_title="Audit campaign connector and audience",
                action_description=(
                    "Validate message provider health, remove stale contacts, and run a small canary before full dispatch."
                ),
                action_payload={"target": "campaigns", "failure_ratio": campaigns_failed / max(campaigns_sent, 1)},
            )
        )

    if orders_count >= 5 and repeat_ratio < 0.2:
        candidates.append(
            InsightCandidate(
                insight_type="opportunity",
                severity="medium",
                title="Repeat-customer conversion can be improved",
                summary=(
                    f"Only {repeat_customers} repeat customers across {orders_count} orders. "
                    "Retention nudges can improve predictable revenue."
                ),
                confidence_score=0.82,
                context_json={"repeat_customers": repeat_customers, "orders_count": orders_count},
                action_type="retention_campaign",
                action_title="Launch repeat-customer nudge",
                action_description=(
                    "Trigger a targeted retention campaign to customers with one completed purchase in the last 30 days."
                ),
                action_payload={"target": "retention", "channel_preference": "whatsapp"},
            )
        )

    if net_revenue > 0 and margin_rate < 0.2:
        candidates.append(
            InsightCandidate(
                insight_type="urgency",
                severity="medium",
                title="Net margin is below target guardrail",
                summary=(
                    f"Estimated net margin is {margin_rate * 100:.1f}% in the active window. "
                    "Expense controls and pricing optimization are needed."
                ),
                confidence_score=0.79,
                context_json={"margin_rate": margin_rate, "net_revenue": net_revenue, "expenses_total": expenses_total},
                action_type="margin_protection",
                action_title="Apply margin protection checklist",
                action_description=(
                    "Pause low-margin discounts, renegotiate input costs, and adjust pricing for top volume SKUs."
                ),
                action_payload={"target": "margin", "minimum_margin_rate": 0.2},
            )
        )

    if not candidates:
        candidates.append(
            InsightCandidate(
                insight_type="opportunity",
                severity="low",
                title="Performance is stable with room to scale",
                summary=(
                    "No critical anomaly detected in the active window. Focus on increasing order volume while preserving "
                    "refund quality and margin discipline."
                ),
                confidence_score=0.72,
                context_json={
                    "paid_ratio": paid_ratio,
                    "refund_rate": refund_rate,
                    "margin_rate": margin_rate,
                },
                action_type="growth_experiment",
                action_title="Run controlled growth experiment",
                action_description=(
                    "Select one high-performing channel and test a constrained campaign with tracked conversion goals."
                ),
                action_payload={"target": "growth", "experiment_window_days": 7},
            )
        )
    return candidates


def _normalize_channels(channels: list[str] | None) -> list[str]:
    allowed = {"in_app", "email", "whatsapp"}
    normalized: list[str] = []
    for channel in channels or []:
        cleaned = str(channel or "").strip().lower()
        if cleaned in allowed and cleaned not in normalized:
            normalized.append(cleaned)
    if not normalized:
        normalized.append("in_app")
    return normalized


def _curated_metrics(
    db: Session,
    *,
    business_id: str,
    snapshot: AIFeatureSnapshot,
) -> list[CuratedMetric]:
    start_date = snapshot.window_start_date
    end_date = snapshot.window_end_date
    metrics_row = db.execute(
        select(
            func.coalesce(func.sum(AnalyticsDailyMetric.revenue), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.net_profit), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.orders_count), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.repeat_orders_count), 0),
        ).where(
            AnalyticsDailyMetric.business_id == business_id,
            AnalyticsDailyMetric.metric_date >= start_date,
            AnalyticsDailyMetric.metric_date <= end_date,
        )
    ).one()
    total_revenue = float(to_money(metrics_row[0] or 0))
    total_net_profit = float(to_money(metrics_row[1] or 0))
    total_orders = int(metrics_row[2] or 0)
    total_repeat_orders = int(metrics_row[3] or 0)
    avg_order_value = 0.0 if total_orders <= 0 else total_revenue / max(total_orders, 1)
    repeat_rate = 0.0 if total_orders <= 0 else total_repeat_orders / max(total_orders, 1)

    channel_revenue = func.coalesce(func.sum(AnalyticsDailyMetric.revenue), 0).label("channel_revenue")
    top_channel_row = db.execute(
        select(AnalyticsDailyMetric.channel, channel_revenue)
        .where(
            AnalyticsDailyMetric.business_id == business_id,
            AnalyticsDailyMetric.metric_date >= start_date,
            AnalyticsDailyMetric.metric_date <= end_date,
        )
        .group_by(AnalyticsDailyMetric.channel)
        .order_by(channel_revenue.desc())
        .limit(1)
    ).first()
    top_channel = top_channel_row[0] if top_channel_row else "unknown"
    campaigns_failure_rate = 0.0
    if int(snapshot.campaigns_sent_count or 0) > 0:
        campaigns_failure_rate = int(snapshot.campaigns_failed_count or 0) / max(
            int(snapshot.campaigns_sent_count or 0),
            1,
        )

    return [
        CuratedMetric(key="total_revenue", value=round(total_revenue, 2), source="analytics_daily_metrics"),
        CuratedMetric(key="total_net_profit", value=round(total_net_profit, 2), source="analytics_daily_metrics"),
        CuratedMetric(key="total_orders", value=total_orders, source="analytics_daily_metrics"),
        CuratedMetric(key="average_order_value", value=round(avg_order_value, 2), source="analytics_daily_metrics"),
        CuratedMetric(key="repeat_order_rate", value=round(repeat_rate, 4), source="analytics_daily_metrics"),
        CuratedMetric(key="top_channel", value=top_channel, source="analytics_daily_metrics"),
        CuratedMetric(key="refund_rate", value=round(float(snapshot.refund_rate or 0), 4), source="ai_feature_snapshots"),
        CuratedMetric(
            key="stockout_events_count",
            value=int(snapshot.stockout_events_count or 0),
            source="ai_feature_snapshots",
        ),
        CuratedMetric(
            key="campaign_failure_rate",
            value=round(campaigns_failure_rate, 4),
            source="ai_feature_snapshots",
        ),
    ]


def _answer_curated_metrics_question(question: str, metrics: list[CuratedMetric]) -> str:
    metric_map = {item.key: item.value for item in metrics}
    q = question.lower()
    total_revenue = float(metric_map.get("total_revenue", 0))
    total_net_profit = float(metric_map.get("total_net_profit", 0))
    total_orders = int(metric_map.get("total_orders", 0))
    avg_order_value = float(metric_map.get("average_order_value", 0))
    repeat_rate = float(metric_map.get("repeat_order_rate", 0))
    top_channel = str(metric_map.get("top_channel", "unknown"))
    refund_rate = float(metric_map.get("refund_rate", 0))
    stockout_events = int(metric_map.get("stockout_events_count", 0))
    campaign_failure_rate = float(metric_map.get("campaign_failure_rate", 0))
    margin_pct = 0.0 if total_revenue <= 0 else (total_net_profit / max(total_revenue, 1)) * 100

    prefix = "Grounded in curated metrics: "
    if "profit" in q or "margin" in q:
        return (
            f"{prefix}net profit is {total_net_profit:.2f} on revenue {total_revenue:.2f} "
            f"(margin {margin_pct:.1f}%)."
        )
    if "revenue" in q or "sales" in q:
        return (
            f"{prefix}revenue is {total_revenue:.2f} across {total_orders} orders "
            f"(average order value {avg_order_value:.2f})."
        )
    if "refund" in q:
        return f"{prefix}refund rate is {refund_rate * 100:.1f}% for the active analysis window."
    if "stock" in q or "inventory" in q:
        return f"{prefix}{stockout_events} variants are currently at/under reorder threshold."
    if "channel" in q:
        return f"{prefix}top channel by revenue is {top_channel}."
    if "campaign" in q:
        return f"{prefix}campaign failure rate is {campaign_failure_rate * 100:.1f}%."
    if "repeat" in q or "retention" in q:
        return f"{prefix}repeat-order rate is {repeat_rate * 100:.1f}%."
    return (
        f"{prefix}revenue {total_revenue:.2f}, net profit {total_net_profit:.2f}, "
        f"refund rate {refund_rate * 100:.1f}%, stockout alerts {stockout_events}, top channel {top_channel}."
    )


def _load_permitted_snapshot(db: Session, business_id: str) -> PermittedBusinessSnapshot:
    sales_total = db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.business_id == business_id)
    ).scalar_one()
    sales_count = db.execute(
        select(func.count(Sale.id)).where(
            Sale.business_id == business_id,
            Sale.kind == "sale",
        )
    ).scalar_one()
    expense_total = db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.business_id == business_id)
    ).scalar_one()
    expense_count = db.execute(
        select(func.count(Expense.id)).where(Expense.business_id == business_id)
    ).scalar_one()

    channel_count = func.count(Sale.id).label("channel_count")
    top_channel_row = db.execute(
        select(Sale.channel, channel_count)
        .where(Sale.business_id == business_id, Sale.kind == "sale")
        .group_by(Sale.channel)
        .order_by(channel_count.desc())
        .limit(1)
    ).first()

    payment_count = func.count(Sale.id).label("payment_count")
    top_payment_row = db.execute(
        select(Sale.payment_method, payment_count)
        .where(Sale.business_id == business_id, Sale.kind == "sale")
        .group_by(Sale.payment_method)
        .order_by(payment_count.desc())
        .limit(1)
    ).first()

    sales_total_f = float(to_money(sales_total))
    expense_total_f = float(to_money(expense_total))
    sales_count_i = int(sales_count)

    average_sale_value = 0.0
    if sales_count_i > 0:
        average_sale_value = sales_total_f / sales_count_i

    feature_snapshot = latest_feature_snapshot(db, business_id)
    if feature_snapshot is None:
        window_start_date, window_end_date = _resolve_window(30)
        feature_metrics = _compute_feature_snapshot_metrics(
            db,
            business_id=business_id,
            window_start_date=window_start_date,
            window_end_date=window_end_date,
        )
        orders_count_window = feature_metrics.orders_count
        paid_orders_count_window = feature_metrics.paid_orders_count
        refund_rate_window = feature_metrics.refund_rate
        stockout_events_window = feature_metrics.stockout_events_count
        campaigns_sent_window = feature_metrics.campaigns_sent_count
        campaigns_failed_window = feature_metrics.campaigns_failed_count
        repeat_customers_window = feature_metrics.repeat_customers_count
        net_revenue_window = float(to_money(feature_metrics.net_revenue))
        expenses_window = float(to_money(feature_metrics.expenses_total))
    else:
        orders_count_window = int(feature_snapshot.orders_count or 0)
        paid_orders_count_window = int(feature_snapshot.paid_orders_count or 0)
        refund_rate_window = float(feature_snapshot.refund_rate or 0)
        stockout_events_window = int(feature_snapshot.stockout_events_count or 0)
        campaigns_sent_window = int(feature_snapshot.campaigns_sent_count or 0)
        campaigns_failed_window = int(feature_snapshot.campaigns_failed_count or 0)
        repeat_customers_window = int(feature_snapshot.repeat_customers_count or 0)
        net_revenue_window = float(to_money(feature_snapshot.net_revenue or 0))
        expenses_window = float(to_money(feature_snapshot.expenses_total or 0))

    return PermittedBusinessSnapshot(
        sales_total=sales_total_f,
        sales_count=sales_count_i,
        average_sale_value=average_sale_value,
        expense_total=expense_total_f,
        expense_count=int(expense_count),
        profit_simple=sales_total_f - expense_total_f,
        top_sales_channel=top_channel_row[0] if top_channel_row else None,
        top_payment_method=top_payment_row[0] if top_payment_row else None,
        orders_count_window=orders_count_window,
        paid_orders_count_window=paid_orders_count_window,
        refund_rate_window=refund_rate_window,
        stockout_events_window=stockout_events_window,
        campaigns_sent_window=campaigns_sent_window,
        campaigns_failed_window=campaigns_failed_window,
        repeat_customers_window=repeat_customers_window,
        net_revenue_window=net_revenue_window,
        expenses_window=expenses_window,
    )


def _build_log(
    *,
    business_id: str,
    insight_type: str,
    prompt: str,
    response: str,
    provider: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    estimated_cost_usd: float | None,
    metadata_json: dict[str, Any] | None,
) -> AIInsightLog:
    return AIInsightLog(
        id=str(uuid.uuid4()),
        business_id=business_id,
        insight_type=insight_type,
        prompt=prompt,
        response=response,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        metadata_json=metadata_json,
    )


def _compose_prompt(system_prompt: str, user_prompt: str) -> str:
    return f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"


def _insight_system_prompt() -> str:
    return (
        "You are an assistant for informal business operators. "
        "Use only ALLOWED_FIELDS_JSON. "
        "Do not infer data outside these fields. "
        "Respond with practical guidance."
    )


def _ask_system_prompt() -> str:
    return (
        "You are an assistant for informal business operators. "
        "Answer strictly from ALLOWED_FIELDS_JSON. "
        "If a question requires unavailable fields, say so explicitly."
    )


def _daily_insight_user_prompt(context: dict[str, Any]) -> str:
    return (
        "TASK: daily_insight\n"
        f"ALLOWED_FIELDS_JSON: {json.dumps(context, sort_keys=True)}\n"
        "Return exactly 3 actionable bullet points."
    )


def _ask_user_prompt(context: dict[str, Any], question: str) -> str:
    return (
        "TASK: question_answer\n"
        f"ALLOWED_FIELDS_JSON: {json.dumps(context, sort_keys=True)}\n"
        f"QUESTION: {question}\n"
        "Return a concise answer."
    )


def _get_provider() -> AIProvider:
    provider_name = settings.ai_provider.strip().lower()
    if provider_name == "stub":
        return StubAIProvider(model=settings.ai_model)
    if provider_name == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.ai_model,
            base_url=settings.openai_base_url,
        )
    raise ValueError(f"Unsupported ai_provider: {settings.ai_provider}")
