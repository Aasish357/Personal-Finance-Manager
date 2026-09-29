"""
Analytics endpoints.

These used to pull every one of the caller's transactions into Python and sum
them there. That is fine at a few hundred rows and falls over at tens of
thousands -- and budget-vs-actual was quadratic, scanning the full transaction
list once per budget.

The work is now done in SQL with GROUP BY, so the database returns a handful of
rows regardless of how much history exists. The response shapes are unchanged.

Portability: grouping by calendar month uses func.extract('year'|'month'), which
Postgres and SQLite (3.9+) both support. date_trunc/strftime would be faster on
one dialect each but would need branching, and the row count is already the
bottleneck.
"""
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.db.models.alert import Alert
from app.db.models.budget import Budget
from app.db.models.category import Category
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.utils.helpers import calculate_budget_utilization

router = APIRouter()

_YEAR = func.extract("year", Transaction.transaction_date)
_MONTH = func.extract("month", Transaction.transaction_date)

UNCATEGORIZED = "uncategorized"


def _income() -> object:
    """SUM(amount) over income rows only."""
    return func.sum(
        case((Transaction.transaction_type == "income", Transaction.amount), else_=0)
    )


def _expense() -> object:
    return func.sum(
        case((Transaction.transaction_type == "expense", Transaction.amount), else_=0)
    )


def _own_category_names(db: Session, user_id: str) -> dict[str, str]:
    return {
        c.id: c.name
        for c in db.query(Category).filter(Category.user_id == user_id).all()
    }


@router.get("/monthly")
async def get_monthly_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Income vs. expense totals grouped by calendar month, oldest first."""
    rows = (
        db.query(
            _YEAR.label("y"),
            _MONTH.label("m"),
            _income().label("income"),
            _expense().label("expense"),
        )
        .filter(Transaction.user_id == current_user.id)
        .group_by(_YEAR, _MONTH)
        .order_by(_YEAR, _MONTH)
        .all()
    )

    return [
        {
            "month": f"{int(r.y):04d}-{int(r.m):02d}",
            "income": round(float(r.income or 0), 2),
            "expense": round(float(r.expense or 0), 2),
            "net": round(float(r.income or 0) - float(r.expense or 0), 2),
        }
        for r in rows
    ]


@router.get("/categories")
async def get_category_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Expense totals grouped by category, across all time, highest spend first."""
    rows = (
        db.query(
            func.coalesce(Transaction.category_id, UNCATEGORIZED).label("cid"),
            func.sum(Transaction.amount).label("amount"),
        )
        .filter(Transaction.user_id == current_user.id, Transaction.transaction_type == "expense")
        .group_by(func.coalesce(Transaction.category_id, UNCATEGORIZED))
        .all()
    )
    names = _own_category_names(db, current_user.id)

    totals = {r.cid: float(r.amount or 0) for r in rows}
    total_spent = sum(totals.values())

    result = [
        {
            "category_id": cid,
            "category_name": names.get(cid, "Uncategorized"),
            "amount": round(amount, 2),
            "percentage": round((amount / total_spent) * 100, 1) if total_spent else 0,
        }
        for cid, amount in totals.items()
    ]
    return sorted(result, key=lambda r: r["amount"], reverse=True)


@router.get("/budget-vs-actual")
async def get_budget_vs_actual(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    For every budget the user has set, how much they've actually spent in that
    category/month.

    Spend is aggregated once into a (category, year, month) -> amount map and
    then looked up per budget, so the cost no longer scales with
    budgets x transactions.
    """
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    names = _own_category_names(db, current_user.id)

    spend_rows = (
        db.query(
            Transaction.category_id.label("cid"),
            _YEAR.label("y"),
            _MONTH.label("m"),
            func.sum(Transaction.amount).label("amount"),
        )
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == "expense",
            Transaction.category_id.isnot(None),
        )
        .group_by(Transaction.category_id, _YEAR, _MONTH)
        .all()
    )
    spend = {
        (r.cid, int(r.y), int(r.m)): float(r.amount or 0)
        for r in spend_rows
        if r.cid
    }

    result = []
    for b in budgets:
        spent = spend.get((b.category_id, b.month.year, b.month.month), 0.0)
        budgeted = float(b.amount)
        result.append(
            {
                "budget_id": b.id,
                "category_id": b.category_id,
                "category_name": names.get(b.category_id, "Uncategorized"),
                "month": f"{b.month.year:04d}-{b.month.month:02d}",
                "budgeted": budgeted,
                "spent": round(spent, 2),
                "utilization_pct": round(calculate_budget_utilization(spent, budgeted), 1),
            }
        )
    return sorted(result, key=lambda r: r["month"], reverse=True)


@router.get("/overview")
async def get_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Top-line numbers for the dashboard: all-time balance, this month's activity, active alerts."""
    all_time = (
        db.query(
            _income().label("income"),
            _expense().label("expense"),
            func.count(Transaction.id).label("count"),
        )
        .filter(Transaction.user_id == current_user.id)
        .one()
    )
    total_income = float(all_time.income or 0)
    total_expense = float(all_time.expense or 0)

    now = datetime.now(timezone.utc)
    this_month = (
        db.query(
            _income().label("income"),
            _expense().label("expense"),
        )
        .filter(
            Transaction.user_id == current_user.id,
            _YEAR == now.year,
            _MONTH == now.month,
        )
        .one()
    )
    month_income = float(this_month.income or 0)
    month_expense = float(this_month.expense or 0)

    active_alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.status == "active")
        .count()
    )

    return {
        "balance": round(total_income - total_expense, 2),
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "current_month_income": round(month_income, 2),
        "current_month_expense": round(month_expense, 2),
        "active_alerts": active_alerts,
        "transaction_count": int(all_time.count or 0),
    }