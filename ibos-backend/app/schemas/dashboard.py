from datetime import date

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    sales_total: float
    sales_count: int
    average_sale_value: float
    expense_total: float
    expense_count: int
    profit_simple: float
    start_date: date | None = None
    end_date: date | None = None


class DashboardTopCustomerOut(BaseModel):
    customer_id: str
    customer_name: str
    total_spent: float
    transactions: int


class DashboardCustomerInsightsOut(BaseModel):
    repeat_buyers: int
    active_customers: int
    total_customers: int
    top_customers: list[DashboardTopCustomerOut]
    start_date: date | None = None
    end_date: date | None = None
