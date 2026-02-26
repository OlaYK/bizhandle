import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.money import to_money
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_business, get_current_user
from app.models.expense import Expense
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseCreateOut,
    ExpenseListOut,
    ExpenseOut,
    ExpenseUpdate,
)
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post(
    "",
    response_model=ExpenseCreateOut,
    summary="Create expense",
    responses=error_responses(400, 401, 403, 422, 500),
)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    biz = access.business
    e = Expense(
        id=str(uuid.uuid4()),
        business_id=biz.id,
        category=payload.category,
        amount=to_money(payload.amount),
        note=payload.note,
    )
    db.add(e)
    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="expense.create",
        target_type="expense",
        target_id=e.id,
        metadata_json={"category": e.category, "amount": float(to_money(e.amount))},
    )
    db.commit()
    return ExpenseCreateOut(id=e.id)


@router.patch(
    "/{expense_id}",
    response_model=ExpenseOut,
    summary="Update expense",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def update_expense(
    expense_id: str,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    biz = access.business
    expense = db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.business_id == biz.id,
        )
    ).scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    changes: dict[str, object] = {}
    if payload.category is not None:
        expense.category = payload.category
        changes["category"] = payload.category
    if payload.amount is not None:
        normalized = to_money(payload.amount)
        expense.amount = normalized
        changes["amount"] = float(normalized)
    if "note" in payload.model_fields_set:
        expense.note = payload.note
        changes["note"] = payload.note

    if not changes:
        raise HTTPException(status_code=400, detail="No update fields provided")

    log_audit_event(
        db,
        business_id=biz.id,
        actor_user_id=actor.id,
        action="expense.update",
        target_type="expense",
        target_id=expense.id,
        metadata_json=changes,
    )
    db.commit()
    db.refresh(expense)
    return ExpenseOut(
        id=expense.id,
        category=expense.category,
        amount=float(to_money(expense.amount)),
        note=expense.note,
        created_at=expense.created_at,
    )


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
