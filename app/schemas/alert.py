from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertBase(BaseModel):
    budget_id: str
    category_id: str
    threshold: str  # e.g. "75%"
    utilization: float
    status: str = "active"


class AlertCreate(AlertBase):
    pass


class Alert(AlertBase):
    id: str
    user_id: str
    triggered_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
