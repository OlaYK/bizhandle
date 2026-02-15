from sqlalchemy import String, DateTime, func, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)

    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)  # cash/transfer/pos
    channel: Mapped[str] = mapped_column(String(30), nullable=False)         # whatsapp/instagram/walk-in
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sale_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales.id"), index=True)
    variant_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_variants.id"), index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
