from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.db.models.category import Category
from app.db.models.transaction import Transaction as DBTransaction
from app.db.models.user import User
from app.schemas.transaction import Transaction, TransactionCreate, TransactionUpdate
from app.utils.budget_alerts import reconcile_budget_alerts

router = APIRouter()

# A caller that omits limit/offset still receives every row, so the default is
# deliberately generous; MAX_PAGE_SIZE caps what a client can ask for.
DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500


def _month_start(moment: datetime) -> datetime:
    """First instant of the month containing `moment`, for budget lookups."""
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.post("/transactions", response_model=Transaction, status_code=201)
async def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # A transaction may only reference one of the caller's own categories.
    if transaction.category_id:
        owned = (
            db.query(Category)
            .filter(
                Category.id == transaction.category_id,
                Category.user_id == current_user.id,
            )
            .first()
        )
        if owned is None:
            raise HTTPException(status_code=404, detail="Category not found")

    new_transaction = DBTransaction(**transaction.model_dump(), user_id=current_user.id)
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    # An expense against a budgeted category may push utilization past a
    # threshold; check and raise an alert automatically if so.
    if new_transaction.transaction_type == "expense" and new_transaction.category_id:
        month_of = _month_start(new_transaction.transaction_date)
        reconcile_budget_alerts(db, current_user.id, new_transaction.category_id, month_of)

    return new_transaction


@router.get("/transactions", response_model=List[Transaction])
async def get_transactions(
    response: Response,
    category_id: Optional[str] = None,
    transaction_type: Optional[str] = None,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transactions, newest first.

    `limit`/`offset` are optional and the response stays a plain JSON array, so
    existing callers are unaffected -- a caller that passes neither still gets
    every row, exactly as before. The unpaginated total is returned in the
    X-Total-Count header so a client can render page controls without a second
    request.
    """
    query = db.query(DBTransaction).filter(DBTransaction.user_id == current_user.id)
    if category_id:
        query = query.filter(DBTransaction.category_id == category_id)
    if transaction_type:
        query = query.filter(DBTransaction.transaction_type == transaction_type)

    # Count before slicing, and over the same filters, so paging stays correct
    # when a filter is active.
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    rows = (
        query.order_by(DBTransaction.transaction_date.desc(), DBTransaction.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@router.get("/transactions/{transaction_id}", response_model=Transaction)
async def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = (
        db.query(DBTransaction)
        .filter(DBTransaction.id == transaction_id, DBTransaction.user_id == current_user.id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.patch("/transactions/{transaction_id}", response_model=Transaction)
async def update_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = (
        db.query(DBTransaction)
        .filter(DBTransaction.id == transaction_id, DBTransaction.user_id == current_user.id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    changes = payload.model_dump(exclude_unset=True)

    # A category may only be set to one the caller owns. Note an explicit null
    # clears the category, which is legitimate (back to "Uncategorized").
    if changes.get("category_id"):
        owned = (
            db.query(Category)
            .filter(
                Category.id == changes["category_id"],
                Category.user_id == current_user.id,
            )
            .first()
        )
        if owned is None:
            raise HTTPException(status_code=404, detail="Category not found")

    was_expense = transaction.transaction_type == "expense"
    old_month = _month_start(transaction.transaction_date)
    old_category_id = transaction.category_id

    for field, value in changes.items():
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)

    # An edit can move spending between categories or months, so reconcile
    # both the old bucket (which may now be over-reported) and the new one.
    now_expense = transaction.transaction_type == "expense"
    for category_id, month_of in {
        (old_category_id, old_month),
        (transaction.category_id, _month_start(transaction.transaction_date)),
    }:
        if category_id and (now_expense or was_expense):
            reconcile_budget_alerts(db, current_user.id, category_id, month_of)

    return transaction


@router.delete("/transactions/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = (
        db.query(DBTransaction)
        .filter(DBTransaction.id == transaction_id, DBTransaction.user_id == current_user.id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Capture the coordinates before the row is gone, so the affected budget can
    # be re-evaluated afterwards.
    affected = (
        transaction.transaction_type == "expense",
        transaction.category_id,
        _month_start(transaction.transaction_date),
    )

    db.delete(transaction)
    db.commit()

    # Removing an expense can drop utilization back under a threshold that was
    # previously crossed. Reconcile so the alerts page can't keep showing an
    # "active" alert for a budget that is no longer over.
    was_expense, category_id, month_of = affected
    if was_expense and category_id:
        reconcile_budget_alerts(db, current_user.id, category_id, month_of)

    return None
