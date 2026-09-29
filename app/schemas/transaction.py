from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionBase(BaseModel):
    amount: float = Field(gt=0)
    transaction_type: Literal["income", "expense"]
    description: Optional[str] = None
    merchant: Optional[str] = None
    category_id: Optional[str] = None
    transaction_date: datetime


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    """
    Every field optional, so a PATCH can change just the amount or just the
    category without resending the whole row. `id` and `user_id` are not
    updatable.
    """

    amount: Optional[float] = Field(default=None, gt=0)
    transaction_type: Optional[Literal["income", "expense"]] = None
    description: Optional[str] = None
    merchant: Optional[str] = None
    category_id: Optional[str] = None
    transaction_date: Optional[datetime] = None


class Transaction(TransactionBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
