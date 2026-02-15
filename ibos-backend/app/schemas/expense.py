from pydantic import BaseModel
from typing import Optional

class ExpenseCreate(BaseModel):
    category: str
    amount: float
    note: Optional[str] = None
