from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.db.mixins import TimestampMixin, gen_uuid


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    transaction_type = Column(String, nullable=False)  # "income" or "expense"
    description = Column(String)
    merchant = Column(String)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    transaction_date = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
