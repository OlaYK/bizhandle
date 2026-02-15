from sqlalchemy import String, DateTime, func, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(36), ForeignKey("businesses.id"), index=True)

    category: Mapped[str] = mapped_column(String(50), nullable=False)  # logistics, rent, marketing...
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
