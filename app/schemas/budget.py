from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BudgetBase(BaseModel):
    category_id: str
    month: datetime  # first-of-month timestamp, e.g. 2024-10-01T00:00:00
    amount: float = Field(gt=0)


class BudgetCreate(BudgetBase):
    pass


class Budget(BudgetBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
