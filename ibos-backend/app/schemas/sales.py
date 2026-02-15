from pydantic import BaseModel
from typing import List

class SaleItemIn(BaseModel):
    variant_id: str
    qty: int
    unit_price: float

class SaleCreate(BaseModel):
    payment_method: str
    channel: str
    items: List[SaleItemIn]
