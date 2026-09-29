from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.db.mixins import TimestampMixin, gen_uuid


class Budget(Base, TimestampMixin):
    __tablename__ = "budgets"
    # One budget per user per category per month. Without this, a second POST
    # for the same month silently double-counts in budget-vs-actual.
    __table_args__ = (UniqueConstraint("user_id", "category_id", "month", name="uq_budget_user_category_month"),)

    id = Column(String, primary_key=True, index=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    month = Column(DateTime(timezone=True), index=True, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    user = relationship("User", back_populates="budgets")
    category = relationship("Category", back_populates="budgets")
