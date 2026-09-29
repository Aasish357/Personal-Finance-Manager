from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.db.mixins import TimestampMixin, gen_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=gen_uuid)
    name = Column(String, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
