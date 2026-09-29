from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.db.mixins import TimestampMixin, gen_uuid


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    # Categories are per-user. They used to be global, which let any
    # authenticated user list and delete everyone else's categories.
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    id = Column(String, primary_key=True, index=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    # Unique per user rather than globally, so two people can each have
    # "Groceries" without colliding.
    name = Column(String, nullable=False)

    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")
