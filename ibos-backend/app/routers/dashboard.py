from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.security_current import get_current_business
from app.schemas.dashboard import DashboardSummaryOut
from app.services.dashboard_service import get_summary

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
