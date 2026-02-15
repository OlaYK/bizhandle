from sqlalchemy import String, DateTime, func, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), index=True)

    size: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 6by6ft
    label: Mapped[str] = mapped_column(String(100), nullable=True) # e.g., "Plain", "Pattern"
    sku: Mapped[str] = mapped_column(String(100), nullable=True)

    cost_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    selling_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
