from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.db.models.budget import Budget
from app.db.models.category import Category as DBCategory
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.schemas.category import Category, CategoryCreate

router = APIRouter()


@router.get("/categories", response_model=List[Category])
async def list_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Scoped to the caller: categories are per-user, so this must never return
    # anyone else's.
    return (
        db.query(DBCategory)
        .filter(DBCategory.user_id == current_user.id)
        .order_by(DBCategory.name)
        .all()
    )


@router.post("/categories", response_model=Category, status_code=201)
async def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        db.query(DBCategory)
        .filter(DBCategory.user_id == current_user.id, DBCategory.name == category.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")

    new_category = DBCategory(name=category.name, user_id=current_user.id)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # user_id in the filter: a category belonging to someone else must look
    # absent (404), not merely forbidden, so ids can't be probed.
    category = (
        db.query(DBCategory)
        .filter(DBCategory.id == category_id, DBCategory.user_id == current_user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Deleting a category that transactions or budgets still point at makes
    # SQLAlchemy null the foreign keys, which the NOT NULL columns reject --
    # surfacing as a 500. Refuse with a 409 and say what is in the way.
    transaction_count = (
        db.query(Transaction).filter(Transaction.category_id == category_id).count()
    )
    budget_count = db.query(Budget).filter(Budget.category_id == category_id).count()
    if transaction_count or budget_count:
        blockers = []
        if transaction_count:
            blockers.append(f"{transaction_count} transaction{'s' if transaction_count != 1 else ''}")
        if budget_count:
            blockers.append(f"{budget_count} budget{'s' if budget_count != 1 else ''}")
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete '{category.name}': still used by "
                f"{' and '.join(blockers)}. Remove those first, or leave the category in place."
            ),
        )

    db.delete(category)
    db.commit()
    return None
