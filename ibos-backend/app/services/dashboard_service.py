from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.money import ZERO_MONEY, to_money
from app.models.customer import Customer
from app.models.expense import Expense
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.sales import Sale


def get_summary(
    db: Session,
    business_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
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
    expense_count_stmt = select(func.count(Expense.id)).where(
        Expense.business_id == business_id
    )

    if start_date:
        sales_total_stmt = sales_total_stmt.where(func.date(Sale.created_at) >= start_date)
        sales_count_stmt = sales_count_stmt.where(func.date(Sale.created_at) >= start_date)
        expense_total_stmt = expense_total_stmt.where(
            func.date(Expense.created_at) >= start_date
        )
        expense_count_stmt = expense_count_stmt.where(
            func.date(Expense.created_at) >= start_date
        )

    if end_date:
        sales_total_stmt = sales_total_stmt.where(func.date(Sale.created_at) <= end_date)
        sales_count_stmt = sales_count_stmt.where(func.date(Sale.created_at) <= end_date)
        expense_total_stmt = expense_total_stmt.where(func.date(Expense.created_at) <= end_date)
        expense_count_stmt = expense_count_stmt.where(func.date(Expense.created_at) <= end_date)

    sales_total = db.execute(sales_total_stmt).scalar_one() or ZERO_MONEY
    sales_count = db.execute(sales_count_stmt).scalar_one()

    expense_total = db.execute(expense_total_stmt).scalar_one() or ZERO_MONEY
    expense_count = db.execute(expense_count_stmt).scalar_one()

    sales_total_money = to_money(sales_total)
    expense_total_money = to_money(expense_total)
    profit: Decimal = sales_total_money - expense_total_money
    sales_count_i = int(sales_count)
    average_sale_value = (
        to_money(sales_total_money / sales_count_i) if sales_count_i else ZERO_MONEY
    )

    return {
        "sales_total": float(sales_total_money),
        "sales_count": sales_count_i,
        "average_sale_value": float(average_sale_value),
        "expense_total": float(expense_total_money),
        "expense_count": int(expense_count),
        "profit_simple": float(to_money(profit)),
        "start_date": start_date,
        "end_date": end_date,
    }


def get_customer_insights(
    db: Session,
    business_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    total_customers = int(
        db.execute(
            select(func.count(Customer.id)).where(Customer.business_id == business_id)
        ).scalar_one()
    )

    order_totals_stmt = (
        select(
            Order.customer_id,
            func.coalesce(func.sum(Order.total_amount), 0),
            func.count(Order.id),
        )
        .where(
            Order.business_id == business_id,
            Order.customer_id.is_not(None),
            Order.status.in_(["paid", "processing", "fulfilled", "refunded"]),
        )
        .group_by(Order.customer_id)
    )
    if start_date:
        order_totals_stmt = order_totals_stmt.where(func.date(Order.created_at) >= start_date)
    if end_date:
        order_totals_stmt = order_totals_stmt.where(func.date(Order.created_at) <= end_date)

    invoice_event_date = func.coalesce(Invoice.paid_at, Invoice.created_at)
    invoice_totals_stmt = (
        select(
            Invoice.customer_id,
            func.coalesce(func.sum(Invoice.amount_paid), 0),
            func.count(Invoice.id),
        )
        .where(
            Invoice.business_id == business_id,
            Invoice.customer_id.is_not(None),
            Invoice.status == "paid",
            Invoice.amount_paid > 0,
        )
        .group_by(Invoice.customer_id)
    )
    if start_date:
        invoice_totals_stmt = invoice_totals_stmt.where(func.date(invoice_event_date) >= start_date)
    if end_date:
        invoice_totals_stmt = invoice_totals_stmt.where(func.date(invoice_event_date) <= end_date)

    customer_totals: dict[str, dict[str, Decimal | int]] = {}

    for customer_id, total_amount, txn_count in db.execute(order_totals_stmt).all():
        if not customer_id:
            continue
        current = customer_totals.setdefault(
            customer_id,
            {"total_spent": ZERO_MONEY, "transactions": 0},
        )
        current["total_spent"] = to_money(Decimal(current["total_spent"]) + to_money(total_amount))
        current["transactions"] = int(current["transactions"]) + int(txn_count or 0)

    for customer_id, total_amount, txn_count in db.execute(invoice_totals_stmt).all():
        if not customer_id:
            continue
        current = customer_totals.setdefault(
            customer_id,
            {"total_spent": ZERO_MONEY, "transactions": 0},
        )
        current["total_spent"] = to_money(Decimal(current["total_spent"]) + to_money(total_amount))
        current["transactions"] = int(current["transactions"]) + int(txn_count or 0)

    active_customers = len(customer_totals)
    repeat_buyers = sum(
        1 for metrics in customer_totals.values() if int(metrics["transactions"]) >= 2
    )

    sorted_customers = sorted(
        customer_totals.items(),
        key=lambda item: (
            Decimal(item[1]["total_spent"]),
            int(item[1]["transactions"]),
        ),
        reverse=True,
    )
    top_customer_ids = [customer_id for customer_id, _ in sorted_customers[:5]]

    customer_name_map: dict[str, str] = {}
    if top_customer_ids:
        customer_name_rows = db.execute(
            select(Customer.id, Customer.name).where(
                Customer.business_id == business_id,
                Customer.id.in_(top_customer_ids),
            )
        ).all()
        customer_name_map = {customer_id: name for customer_id, name in customer_name_rows}

    top_customers = [
        {
            "customer_id": customer_id,
            "customer_name": customer_name_map.get(customer_id, "Unknown"),
            "total_spent": float(to_money(metrics["total_spent"])),
            "transactions": int(metrics["transactions"]),
        }
        for customer_id, metrics in sorted_customers[:5]
    ]

    return {
        "repeat_buyers": repeat_buyers,
        "active_customers": active_customers,
        "total_customers": total_customers,
        "top_customers": top_customers,
        "start_date": start_date,
        "end_date": end_date,
    }
