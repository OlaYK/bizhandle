from pydantic import BaseModel
from typing import Optional

class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None

class VariantCreate(BaseModel):
    size: str
    label: Optional[str] = None
    sku: Optional[str] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
