from sqlalchemy import Column, String, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.mixins import TimestampMixin, gen_uuid


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, index=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    threshold = Column(String, nullable=False)  # e.g. "75%"
    utilization = Column(Numeric(6, 2), nullable=False)
    status = Column(String, nullable=False, default="active")
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="alerts")
