import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security_current import get_current_business
from app.schemas.expense import ExpenseCreate
from app.models.expense import Expense

router = APIRouter(prefix="/expenses", tags=["expenses"])

@router.post("")
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db), biz=Depends(get_current_business)):
    e = Expense(
        id=str(uuid.uuid4()),
        business_id=biz.id,
        category=payload.category,
        amount=payload.amount,
        note=payload.note,
    )
    db.add(e)
    db.commit()
    return {"id": e.id}
