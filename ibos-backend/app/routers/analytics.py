import csv
import io
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import ZERO_MONEY, to_money
from app.core.permissions import require_permission
from app.core.security_current import BusinessAccess, get_current_user
from app.models.analytics import AnalyticsDailyMetric, AnalyticsReportSchedule, MarketingAttributionEvent
from app.models.expense import Expense
from app.models.inventory import InventoryLedger
from app.models.order import Order
from app.models.product import ProductVariant
from app.models.sales import Sale, SaleItem
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsMartRefreshOut,
    ChannelProfitabilityItemOut,
    ChannelProfitabilityOut,
    CohortRetentionItemOut,
    CohortRetentionOut,
    InventoryAgingItemOut,
    InventoryAgingOut,
    MarketingAttributionEventIn,
    MarketingAttributionEventOut,
    ReportExportOut,
    ReportScheduleCreateIn,
    ReportScheduleListOut,
    ReportScheduleOut,
)
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/analytics", tags=["analytics"])

TRACKED_ORDER_STATUSES = {"pending", "paid", "processing", "fulfilled", "refunded"}
ALLOWED_REPORT_TYPES = {"channel_profitability", "cohorts", "inventory_aging"}


def _coerce_day(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported day value type: {type(value)!r}")


def _validate_date_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=30))
    if resolved_end < resolved_start:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")
    return resolved_start, resolved_end


def _as_of_end_datetime(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _upsert_daily_metric(
    db: Session,
    *,
    business_id: str,
    metric_date: date,
    channel: str,
    revenue: Decimal,
    cogs: Decimal,
    expenses: Decimal,
    orders_count: int,
    repeat_orders_count: int,
    stockout_events_count: int,
) -> AnalyticsDailyMetric:
    row = db.execute(
        select(AnalyticsDailyMetric).where(
            AnalyticsDailyMetric.business_id == business_id,
            AnalyticsDailyMetric.metric_date == metric_date,
            AnalyticsDailyMetric.channel == channel,
        )
    ).scalar_one_or_none()
    gross_profit = to_money(revenue - cogs)
    net_profit = to_money(gross_profit - expenses)
    if row is None:
        row = AnalyticsDailyMetric(
            id=str(uuid.uuid4()),
            business_id=business_id,
            metric_date=metric_date,
            channel=channel,
            revenue=to_money(revenue),
            cogs=to_money(cogs),
            expenses=to_money(expenses),
            gross_profit=gross_profit,
            net_profit=net_profit,
            orders_count=int(orders_count),
            repeat_orders_count=int(repeat_orders_count),
            stockout_events_count=int(stockout_events_count),
        )
        db.add(row)
        return row

    row.revenue = to_money(revenue)
    row.cogs = to_money(cogs)
    row.expenses = to_money(expenses)
    row.gross_profit = gross_profit
    row.net_profit = net_profit
    row.orders_count = int(orders_count)
    row.repeat_orders_count = int(repeat_orders_count)
    row.stockout_events_count = int(stockout_events_count)
    return row


def _refresh_daily_metrics(
    db: Session,
    *,
    business_id: str,
    start_date: date,
    end_date: date,
) -> int:
    db.execute(
        delete(AnalyticsDailyMetric).where(
            AnalyticsDailyMetric.business_id == business_id,
            AnalyticsDailyMetric.metric_date >= start_date,
            AnalyticsDailyMetric.metric_date <= end_date,
        )
    )

    order_rows = db.execute(
        select(
            func.date(Order.created_at),
            Order.channel,
            func.coalesce(func.sum(Order.total_amount), 0),
            func.count(Order.id),
        ).where(
            Order.business_id == business_id,
            Order.status.in_(list(TRACKED_ORDER_STATUSES)),
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
        )
        .group_by(func.date(Order.created_at), Order.channel)
    ).all()

    customer_repeat_rows = db.execute(
        select(
            func.date(Order.created_at),
            Order.channel,
            Order.customer_id,
            func.count(Order.id),
        ).where(
            Order.business_id == business_id,
            Order.status.in_(list(TRACKED_ORDER_STATUSES)),
            Order.customer_id.is_not(None),
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
        )
        .group_by(func.date(Order.created_at), Order.channel, Order.customer_id)
    ).all()
    repeat_map: dict[tuple[date, str], int] = defaultdict(int)
    for created_day, channel, _customer_id, count in customer_repeat_rows:
        metric_day = _coerce_day(created_day)
        if int(count or 0) >= 2:
            repeat_map[(metric_day, channel)] += 1

    cogs_rows = db.execute(
        select(
            func.date(Sale.created_at),
            Sale.channel,
            func.coalesce(func.sum(func.coalesce(ProductVariant.cost_price, 0) * SaleItem.qty), 0),
        )
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(ProductVariant, ProductVariant.id == SaleItem.variant_id)
        .where(
            Sale.business_id == business_id,
            Sale.kind == "sale",
            SaleItem.qty > 0,
            func.date(Sale.created_at) >= start_date,
            func.date(Sale.created_at) <= end_date,
        )
        .group_by(func.date(Sale.created_at), Sale.channel)
    ).all()
    cogs_map: dict[tuple[date, str], Decimal] = {
        (_coerce_day(created_day), channel): to_money(value or 0)
        for created_day, channel, value in cogs_rows
    }

    expense_rows = db.execute(
        select(func.date(Expense.created_at), func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.business_id == business_id,
            func.date(Expense.created_at) >= start_date,
            func.date(Expense.created_at) <= end_date,
        )
        .group_by(func.date(Expense.created_at))
    ).all()
    expense_map: dict[date, Decimal] = {
        _coerce_day(created_day): to_money(amount or 0) for created_day, amount in expense_rows
    }

    stockout_count = int(
        db.execute(
            select(func.count(ProductVariant.id)).where(
                ProductVariant.business_id == business_id,
            )
        ).scalar_one()
    )

    revenue_by_day: dict[date, Decimal] = defaultdict(lambda: ZERO_MONEY)
    channels_by_day: dict[date, set[str]] = defaultdict(set)
    base_rows: dict[tuple[date, str], dict] = {}
    for created_day, channel, revenue, orders_count in order_rows:
        metric_day = _coerce_day(created_day)
        normalized_channel = channel or "unknown"
        row_revenue = to_money(revenue or 0)
        key = (metric_day, normalized_channel)
        revenue_by_day[metric_day] = to_money(revenue_by_day[metric_day] + row_revenue)
        channels_by_day[metric_day].add(normalized_channel)
        base_rows[key] = {
            "revenue": row_revenue,
            "orders_count": int(orders_count or 0),
            "repeat_orders_count": int(repeat_map.get(key, 0)),
            "cogs": to_money(cogs_map.get(key, ZERO_MONEY)),
        }

    if not base_rows and expense_map:
        for day, expense_total in expense_map.items():
            base_rows[(day, "unattributed")] = {
                "revenue": ZERO_MONEY,
                "orders_count": 0,
                "repeat_orders_count": 0,
                "cogs": ZERO_MONEY,
            }
            channels_by_day[day].add("unattributed")
            revenue_by_day[day] = ZERO_MONEY

    rows_refreshed = 0
    for (metric_day, channel), payload in base_rows.items():
        expense_total = expense_map.get(metric_day, ZERO_MONEY)
        day_revenue = revenue_by_day.get(metric_day, ZERO_MONEY)
        day_channels = channels_by_day.get(metric_day, set()) or {channel}
        if day_revenue > ZERO_MONEY:
            allocated_expense = to_money(expense_total * (payload["revenue"] / day_revenue))
        else:
            allocated_expense = to_money(expense_total / max(len(day_channels), 1))

        _upsert_daily_metric(
            db,
            business_id=business_id,
            metric_date=metric_day,
            channel=channel,
            revenue=payload["revenue"],
            cogs=payload["cogs"],
            expenses=allocated_expense,
            orders_count=payload["orders_count"],
            repeat_orders_count=payload["repeat_orders_count"],
            stockout_events_count=stockout_count,
        )
        rows_refreshed += 1

    return rows_refreshed


@router.post(
    "/mart/refresh",
    response_model=AnalyticsMartRefreshOut,
    summary="Refresh analytical daily metric mart",
    responses=error_responses(400, 401, 403, 422, 500),
)
def refresh_analytics_mart(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("analytics.refresh")),
    actor: User = Depends(get_current_user),
):
    resolved_start, resolved_end = _validate_date_range(start_date, end_date)
    rows_refreshed = _refresh_daily_metrics(
        db,
        business_id=access.business.id,
        start_date=resolved_start,
        end_date=resolved_end,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="analytics.mart.refresh",
        target_type="analytics_daily_metrics",
        target_id=None,
        metadata_json={
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "rows_refreshed": rows_refreshed,
        },
    )
    db.commit()
    return AnalyticsMartRefreshOut(
        start_date=resolved_start,
        end_date=resolved_end,
        rows_refreshed=rows_refreshed,
    )


@router.get(
    "/channel-profitability",
    response_model=ChannelProfitabilityOut,
    summary="Channel profitability and net margin view",
    responses=error_responses(400, 401, 403, 422, 500),
)
def channel_profitability(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("analytics.view")),
):
    resolved_start, resolved_end = _validate_date_range(start_date, end_date)
    existing_count = int(
        db.execute(
            select(func.count(AnalyticsDailyMetric.id)).where(
                AnalyticsDailyMetric.business_id == access.business.id,
                AnalyticsDailyMetric.metric_date >= resolved_start,
                AnalyticsDailyMetric.metric_date <= resolved_end,
            )
        ).scalar_one()
    )
    if existing_count == 0:
        _refresh_daily_metrics(
            db,
            business_id=access.business.id,
            start_date=resolved_start,
            end_date=resolved_end,
        )
        db.flush()

    rows = db.execute(
        select(
            AnalyticsDailyMetric.channel,
            func.coalesce(func.sum(AnalyticsDailyMetric.revenue), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.cogs), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.expenses), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.gross_profit), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.net_profit), 0),
            func.coalesce(func.sum(AnalyticsDailyMetric.orders_count), 0),
        ).where(
            AnalyticsDailyMetric.business_id == access.business.id,
            AnalyticsDailyMetric.metric_date >= resolved_start,
            AnalyticsDailyMetric.metric_date <= resolved_end,
        )
        .group_by(AnalyticsDailyMetric.channel)
        .order_by(func.sum(AnalyticsDailyMetric.net_profit).desc())
    ).all()

    items: list[ChannelProfitabilityItemOut] = []
    for channel, revenue, cogs, expenses, gross_profit, net_profit, orders_count in rows:
        revenue_money = to_money(revenue or 0)
        net_money = to_money(net_profit or 0)
        margin_pct = float(to_money((net_money / revenue_money) * 100)) if revenue_money > ZERO_MONEY else 0.0
        items.append(
            ChannelProfitabilityItemOut(
                channel=channel,
                revenue=float(revenue_money),
                cogs=float(to_money(cogs or 0)),
                expenses=float(to_money(expenses or 0)),
                gross_profit=float(to_money(gross_profit or 0)),
                net_profit=float(net_money),
                orders_count=int(orders_count or 0),
                margin_pct=margin_pct,
            )
        )
    return ChannelProfitabilityOut(start_date=resolved_start, end_date=resolved_end, items=items)


@router.get(
    "/cohorts",
    response_model=CohortRetentionOut,
    summary="Cohort and repeat-customer retention analytics",
    responses=error_responses(400, 401, 403, 422, 500),
)
def cohort_retention(
    months_after: int = Query(default=1, ge=1, le=12),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("analytics.view")),
):
    order_rows = db.execute(
        select(Order.customer_id, Order.created_at).where(
            Order.business_id == access.business.id,
            Order.customer_id.is_not(None),
            Order.status.in_(list(TRACKED_ORDER_STATUSES)),
        )
    ).all()
    if not order_rows:
        return CohortRetentionOut(months_after=months_after, items=[])

    first_order_month: dict[str, tuple[int, int]] = {}
    activity_by_customer_month: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for customer_id, created_at in order_rows:
        month_key = (created_at.year, created_at.month)
        activity_by_customer_month[customer_id].add(month_key)
        existing = first_order_month.get(customer_id)
        if existing is None or month_key < existing:
            first_order_month[customer_id] = month_key

    cohorts: dict[tuple[int, int], list[str]] = defaultdict(list)
    for customer_id, cohort_key in first_order_month.items():
        cohorts[cohort_key].append(customer_id)

    items: list[CohortRetentionItemOut] = []
    for cohort_key in sorted(cohorts.keys()):
        cohort_year, cohort_month = cohort_key
        target_month_index = cohort_month + months_after
        target_year = cohort_year + ((target_month_index - 1) // 12)
        target_month = ((target_month_index - 1) % 12) + 1

        cohort_customers = cohorts[cohort_key]
        retained = sum(
            1
            for customer_id in cohort_customers
            if (target_year, target_month) in activity_by_customer_month.get(customer_id, set())
        )
        total_customers = len(cohort_customers)
        retention_rate = (retained / total_customers) * 100 if total_customers > 0 else 0
        items.append(
            CohortRetentionItemOut(
                cohort_month=f"{cohort_year:04d}-{cohort_month:02d}",
                total_customers=total_customers,
                retained_customers=retained,
                retention_rate=float(to_money(retention_rate)),
            )
        )
    return CohortRetentionOut(months_after=months_after, items=items)


@router.get(
    "/inventory-aging",
    response_model=InventoryAgingOut,
    summary="Inventory aging and stockout impact analytics",
    responses=error_responses(401, 403, 422, 500),
)
def inventory_aging(
    as_of_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("analytics.view")),
):
    snapshot_date = as_of_date or date.today()
    stock_rows = db.execute(
        select(
            ProductVariant.id,
            ProductVariant.cost_price,
            func.coalesce(func.sum(InventoryLedger.qty_delta), 0),
            func.max(InventoryLedger.created_at),
        )
        .outerjoin(InventoryLedger, InventoryLedger.variant_id == ProductVariant.id)
        .where(ProductVariant.business_id == access.business.id)
        .group_by(ProductVariant.id, ProductVariant.cost_price)
    ).all()

    items: list[InventoryAgingItemOut] = []
    total_value = ZERO_MONEY
    stockout_count = 0
    for variant_id, cost_price, stock, last_movement_at in stock_rows:
        stock_int = int(stock or 0)
        if stock_int <= 0:
            stockout_count += 1
        cost = to_money(cost_price or 0)
        estimated_value = to_money(max(stock_int, 0) * cost)
        total_value += estimated_value

        days_since: int | None = None
        if last_movement_at is not None:
            days_since = max((snapshot_date - last_movement_at.date()).days, 0)
        if days_since is None:
            bucket = "unknown"
        elif days_since <= 30:
            bucket = "0_30"
        elif days_since <= 60:
            bucket = "31_60"
        elif days_since <= 90:
            bucket = "61_90"
        else:
            bucket = "91_plus"

        items.append(
            InventoryAgingItemOut(
                variant_id=variant_id,
                bucket=bucket,
                stock=stock_int,
                estimated_value=float(estimated_value),
                days_since_last_movement=days_since,
            )
        )
    items.sort(key=lambda row: (row.days_since_last_movement or 10_000, -row.stock), reverse=True)
    return InventoryAgingOut(
        as_of_date=snapshot_date,
        stockout_count=stockout_count,
        total_estimated_inventory_value=float(to_money(total_value)),
        items=items,
    )


@router.post(
    "/attribution-events",
    response_model=MarketingAttributionEventOut,
    summary="Ingest marketing attribution event",
    responses=error_responses(400, 401, 403, 422, 500),
)
def ingest_attribution_event(
    payload: MarketingAttributionEventIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("marketing.attribution.ingest")),
    actor: User = Depends(get_current_user),
):
    event = MarketingAttributionEvent(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        event_type=payload.event_type,
        channel=payload.channel,
        source=payload.source,
        medium=payload.medium,
        campaign_name=payload.campaign_name,
        order_id=payload.order_id,
        revenue_amount=to_money(payload.revenue_amount),
        metadata_json=payload.metadata_json,
        event_time=payload.event_time or datetime.now(timezone.utc),
    )
    db.add(event)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="analytics.attribution.ingest",
        target_type="marketing_attribution_event",
        target_id=event.id,
        metadata_json={
            "event_type": event.event_type,
            "channel": event.channel,
            "order_id": event.order_id,
        },
    )
    db.commit()
    db.refresh(event)
    return MarketingAttributionEventOut(
        id=event.id,
        event_type=event.event_type,
        channel=event.channel,
        source=event.source,
        medium=event.medium,
        campaign_name=event.campaign_name,
        order_id=event.order_id,
        revenue_amount=float(to_money(event.revenue_amount)),
        metadata_json=event.metadata_json,
        event_time=event.event_time,
        created_at=event.created_at,
    )


def _export_channel_profitability_csv(
    db: Session,
    *,
    business_id: str,
    start_date: date,
    end_date: date,
) -> tuple[int, str]:
    payload = channel_profitability(
        start_date=start_date,
        end_date=end_date,
        db=db,
        access=BusinessAccess(business=type("Biz", (), {"id": business_id})(), role="owner", membership_id=None),
    )
    writer_io = io.StringIO()
    writer = csv.DictWriter(
        writer_io,
        fieldnames=["channel", "revenue", "cogs", "expenses", "gross_profit", "net_profit", "orders_count", "margin_pct"],
    )
    writer.writeheader()
    for item in payload.items:
        writer.writerow(item.model_dump())
    return len(payload.items), writer_io.getvalue()


def _export_cohorts_csv(
    db: Session,
    *,
    business_id: str,
    months_after: int,
) -> tuple[int, str]:
    payload = cohort_retention(
        months_after=months_after,
        db=db,
        access=BusinessAccess(business=type("Biz", (), {"id": business_id})(), role="owner", membership_id=None),
    )
    writer_io = io.StringIO()
    writer = csv.DictWriter(
        writer_io,
        fieldnames=["cohort_month", "total_customers", "retained_customers", "retention_rate"],
    )
    writer.writeheader()
    for item in payload.items:
        writer.writerow(item.model_dump())
    return len(payload.items), writer_io.getvalue()


def _export_inventory_aging_csv(
    db: Session,
    *,
    business_id: str,
    as_of_date: date,
) -> tuple[int, str]:
    payload = inventory_aging(
        as_of_date=as_of_date,
        db=db,
        access=BusinessAccess(business=type("Biz", (), {"id": business_id})(), role="owner", membership_id=None),
    )
    writer_io = io.StringIO()
    writer = csv.DictWriter(
        writer_io,
        fieldnames=["variant_id", "bucket", "stock", "estimated_value", "days_since_last_movement"],
    )
    writer.writeheader()
    for item in payload.items:
        writer.writerow(item.model_dump())
    return len(payload.items), writer_io.getvalue()


@router.get(
    "/reports/export",
    response_model=ReportExportOut,
    summary="Export analytics report",
    responses=error_responses(400, 401, 403, 422, 500),
)
def export_report(
    report_type: str = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    months_after: int = Query(default=1, ge=1, le=12),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("analytics.report.export")),
):
    normalized_report_type = report_type.strip().lower()
    if normalized_report_type not in ALLOWED_REPORT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_REPORT_TYPES))
        raise HTTPException(status_code=400, detail=f"Invalid report_type. Allowed: {allowed}")

    if normalized_report_type == "channel_profitability":
        resolved_start, resolved_end = _validate_date_range(start_date, end_date)
        row_count, content = _export_channel_profitability_csv(
            db,
            business_id=access.business.id,
            start_date=resolved_start,
            end_date=resolved_end,
        )
    elif normalized_report_type == "cohorts":
        resolved_start, resolved_end = _validate_date_range(start_date, end_date)
        _ = (resolved_start, resolved_end)
        row_count, content = _export_cohorts_csv(
            db,
            business_id=access.business.id,
            months_after=months_after,
        )
    else:
        resolved_start, resolved_end = _validate_date_range(start_date, end_date)
        row_count, content = _export_inventory_aging_csv(
            db,
            business_id=access.business.id,
            as_of_date=resolved_end,
        )

    filename = f"{normalized_report_type}_{date.today().isoformat()}.csv"
    return ReportExportOut(
        filename=filename,
        content_type="text/csv",
        row_count=row_count,
        csv_content=content,
    )


@router.post(
    "/reports/schedules",
    response_model=ReportScheduleOut,
    summary="Create analytics report schedule",
    responses=error_responses(400, 401, 403, 422, 500),
)
def create_report_schedule(
    payload: ReportScheduleCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("analytics.report.schedule")),
    actor: User = Depends(get_current_user),
):
    report_type = payload.report_type.strip().lower()
    if report_type not in ALLOWED_REPORT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_REPORT_TYPES))
        raise HTTPException(status_code=400, detail=f"Invalid report_type. Allowed: {allowed}")

    schedule = AnalyticsReportSchedule(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name,
        report_type=report_type,
        frequency=payload.frequency,
        recipient_email=payload.recipient_email,
        status=payload.status,
        config_json=payload.config_json,
        next_run_at=payload.next_run_at,
    )
    db.add(schedule)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="analytics.report_schedule.create",
        target_type="analytics_report_schedule",
        target_id=schedule.id,
        metadata_json={"report_type": schedule.report_type, "frequency": schedule.frequency},
    )
    db.commit()
    db.refresh(schedule)
    return ReportScheduleOut(
        id=schedule.id,
        name=schedule.name,
        report_type=schedule.report_type,
        frequency=schedule.frequency,
        recipient_email=schedule.recipient_email,
        status=schedule.status,
        config_json=schedule.config_json,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


@router.get(
    "/reports/schedules",
    response_model=ReportScheduleListOut,
    summary="List analytics report schedules",
    responses=error_responses(401, 403, 422, 500),
)
def list_report_schedules(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("analytics.report.schedule")),
):
    stmt = select(AnalyticsReportSchedule).where(
        AnalyticsReportSchedule.business_id == access.business.id
    )
    if status and status.strip():
        stmt = stmt.where(AnalyticsReportSchedule.status == status.strip().lower())
    rows = db.execute(stmt.order_by(AnalyticsReportSchedule.created_at.desc())).scalars().all()
    return ReportScheduleListOut(
        items=[
            ReportScheduleOut(
                id=row.id,
                name=row.name,
                report_type=row.report_type,
                frequency=row.frequency,
                recipient_email=row.recipient_email,
                status=row.status,
                config_json=row.config_json,
                last_run_at=row.last_run_at,
                next_run_at=row.next_run_at,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )
