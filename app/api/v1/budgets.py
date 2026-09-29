from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.db.models.budget import Budget as DBBudget
from app.db.models.category import Category
from app.db.models.user import User
from app.schemas.budget import Budget, BudgetCreate

router = APIRouter()


def _require_own_category(db: Session, user_id: str, category_id: str) -> None:
    """
    Rejects a category that doesn't belong to the caller. Without this, a user
    could attach their budget to (and thereby read the name of) someone else's
    category by passing its id.
    """
    owned = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user_id)
        .first()
    )
    if owned is None:
        raise HTTPException(status_code=404, detail="Category not found")


@router.post("/budgets", response_model=Budget, status_code=201)
async def create_budget(
    budget: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # A budget may only reference one of the caller's own categories.
    _require_own_category(db, current_user.id, budget.category_id)

    # Enforced in the app as well as by the uq_budget_user_category_month
    # constraint, so duplicates are rejected with a clear message (and so this
    # still holds on databases created before the constraint existed).
    duplicate = (
        db.query(DBBudget)
        .filter(
            DBBudget.user_id == current_user.id,
            DBBudget.category_id == budget.category_id,
        )
        .all()
    )
    if any(b.month.year == budget.month.year and b.month.month == budget.month.month for b in duplicate):
        raise HTTPException(
            status_code=409,
            detail="A budget already exists for that category and month. Edit or remove it instead.",
        )

    new_budget = DBBudget(**budget.model_dump(), user_id=current_user.id)
    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)
    return new_budget


@router.get("/budgets", response_model=List[Budget])
async def get_budgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(DBBudget)
        .filter(DBBudget.user_id == current_user.id)
        .order_by(DBBudget.month.desc())
        .all()
    )


@router.delete("/budgets/{budget_id}", status_code=204)
async def delete_budget(
    budget_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = db.query(DBBudget).filter(DBBudget.id == budget_id, DBBudget.user_id == current_user.id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()
    return None
