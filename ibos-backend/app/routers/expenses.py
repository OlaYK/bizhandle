import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import to_money
from app.core.security_current import get_current_business
from app.schemas.common import PaginationMeta
from app.schemas.expense import ExpenseCreate, ExpenseCreateOut, ExpenseListOut, ExpenseOut
from app.models.expense import Expense

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post(
    "",
    response_model=ExpenseCreateOut,
    summary="Create expense",
    responses=error_responses(400, 401, 422, 500),
)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    e = Expense(
        id=str(uuid.uuid4()),
        business_id=biz.id,
        category=payload.category,
        amount=to_money(payload.amount),
        note=payload.note,
    )
    db.add(e)
    db.commit()
    return ExpenseCreateOut(id=e.id)


@router.get(
    "",
    response_model=ExpenseListOut,
    summary="List expenses",
    responses={
        200: {
            "description": "Paginated expenses",
            "content": {
                "application/json": {
                    "example": {
                        "pagination": {
                            "total": 1,
                            "limit": 50,
                            "offset": 0,
                            "count": 1,
                            "has_next": False,
                        },
                        "start_date": None,
                        "end_date": None,
                        "items": [
                            {
                                "id": "expense-id",
                                "category": "logistics",
                                "amount": 25.0,
                                "note": "Dispatch rider payment",
                                "created_at": "2026-02-16T10:00:00Z",
                            }
                        ],
                    }
                }
            },
        },
        **error_responses(400, 401, 422, 500),
    },
)
def list_expenses(
    start_date: date | None = Query(default=None, description="Filter from date (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="Filter to date (YYYY-MM-DD)"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    count_stmt = select(func.count(Expense.id)).where(Expense.business_id == biz.id)
    data_stmt = select(Expense).where(Expense.business_id == biz.id)

    if start_date:
        count_stmt = count_stmt.where(func.date(Expense.created_at) >= start_date)
        data_stmt = data_stmt.where(func.date(Expense.created_at) >= start_date)
    if end_date:
        count_stmt = count_stmt.where(func.date(Expense.created_at) <= end_date)
        data_stmt = data_stmt.where(func.date(Expense.created_at) <= end_date)

    total_count = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        data_stmt.order_by(Expense.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    items = [
        ExpenseOut(
            id=row.id,
            category=row.category,
            amount=float(to_money(row.amount)),
            note=row.note,
            created_at=row.created_at,
        )
        for row in rows
    ]
    count = len(items)

    return ExpenseListOut(
        pagination=PaginationMeta(
            total=total_count,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total_count,
        ),
        start_date=start_date,
        end_date=end_date,
        items=items,
    )
