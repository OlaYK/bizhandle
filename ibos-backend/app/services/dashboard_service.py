from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.money import ZERO_MONEY, to_money
from app.models.sales import Sale
from app.models.expense import Expense


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
