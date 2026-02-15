import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_insight import AIInsightLog
from app.models.expense import Expense
from app.models.sales import Sale


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
        }


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
        estimated_cost_usd = round(
            (total_tokens / 1000) * settings.ai_cost_per_1k_tokens_usd, 6
        )
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

        if sales_total <= 0:
            return (
                "- Record at least 3 sales this week to establish a baseline.\n"
                "- Track expenses by category daily to identify avoidable spend.\n"
                "- Keep payment-method and channel data consistent from today."
            )

        margin_pct = 0.0 if sales_total == 0 else (profit_simple / sales_total) * 100
        return (
            f"- Profit is {profit_simple:.2f} on sales of {sales_total:.2f}; target margin is >20% "
            f"(current {margin_pct:.1f}%).\n"
            f"- Top channel is {top_channel}; prioritize inventory and promotions there.\n"
            f"- Top payment method is {top_payment}; reconcile related transactions daily "
            f"(expenses currently {expense_total:.2f})."
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
        return (
            "I can answer from permitted fields only: sales_total, sales_count, average_sale_value, "
            "expense_total, expense_count, profit_simple, top_sales_channel, top_payment_method."
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
            estimated_cost_usd = round(
                (total_tokens / 1000) * settings.ai_cost_per_1k_tokens_usd,
                6,
            )

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


def _load_permitted_snapshot(db: Session, business_id: str) -> PermittedBusinessSnapshot:
    sales_total = db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.business_id == business_id)
    ).scalar_one()
    sales_count = db.execute(
        select(func.count(Sale.id)).where(Sale.business_id == business_id)
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
        .where(Sale.business_id == business_id)
        .group_by(Sale.channel)
        .order_by(channel_count.desc())
        .limit(1)
    ).first()

    payment_count = func.count(Sale.id).label("payment_count")
    top_payment_row = db.execute(
        select(Sale.payment_method, payment_count)
        .where(Sale.business_id == business_id)
        .group_by(Sale.payment_method)
        .order_by(payment_count.desc())
        .limit(1)
    ).first()

    sales_total_f = float(sales_total)
    expense_total_f = float(expense_total)
    sales_count_i = int(sales_count)

    average_sale_value = 0.0
    if sales_count_i > 0:
        average_sale_value = sales_total_f / sales_count_i

    return PermittedBusinessSnapshot(
        sales_total=sales_total_f,
        sales_count=sales_count_i,
        average_sale_value=average_sale_value,
        expense_total=expense_total_f,
        expense_count=int(expense_count),
        profit_simple=sales_total_f - expense_total_f,
        top_sales_channel=top_channel_row[0] if top_channel_row else None,
        top_payment_method=top_payment_row[0] if top_payment_row else None,
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
