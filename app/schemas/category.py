from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str = Field(min_length=1)


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
