from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.sales import Sale
from app.models.expense import Expense

def get_summary(db: Session, business_id: str) -> dict:
    sales_total = db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.business_id == business_id)
    ).scalar_one()

    expense_total = db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.business_id == business_id)
    ).scalar_one()

    profit = float(sales_total) - float(expense_total)
    return {
        "sales_total": float(sales_total),
        "expense_total": float(expense_total),
        "profit_simple": float(profit),
    }
