from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
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


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


@router.get("/monthly")
async def get_monthly_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Income vs. expense totals grouped by calendar month, oldest first."""
    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()

    by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for t in transactions:
        bucket = by_month[_month_key(t.transaction_date)]
        bucket[t.transaction_type] += float(t.amount)

    return [
        {"month": month, "income": round(v["income"], 2), "expense": round(v["expense"], 2), "net": round(v["income"] - v["expense"], 2)}
        for month, v in sorted(by_month.items())
    ]


@router.get("/categories")
async def get_category_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Expense totals grouped by category, across all time, highest spend first."""
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id, Transaction.transaction_type == "expense")
        .all()
    )
    categories = {
        c.id: c.name
        for c in db.query(Category).filter(Category.user_id == current_user.id).all()
    }

    totals: dict[str, float] = defaultdict(float)
    for t in transactions:
        totals[t.category_id or "uncategorized"] += float(t.amount)

    total_spent = sum(totals.values())
    result = [
        {
            "category_id": cid,
            "category_name": categories.get(cid, "Uncategorized"),
            "amount": round(amount, 2),
            "percentage": round((amount / total_spent) * 100, 1) if total_spent else 0,
        }
        for cid, amount in totals.items()
    ]
    return sorted(result, key=lambda r: r["amount"], reverse=True)


@router.get("/budget-vs-actual")
async def get_budget_vs_actual(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """For every budget the user has set, how much they've actually spent in that category/month."""
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    categories = {
        c.id: c.name
        for c in db.query(Category).filter(Category.user_id == current_user.id).all()
    }
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id, Transaction.transaction_type == "expense")
        .all()
    )

    result = []
    for b in budgets:
        spent = sum(
            float(t.amount)
            for t in transactions
            if t.category_id == b.category_id
            and t.transaction_date.year == b.month.year
            and t.transaction_date.month == b.month.month
        )
        result.append(
            {
                "budget_id": b.id,
                "category_id": b.category_id,
                "category_name": categories.get(b.category_id, "Uncategorized"),
                "month": _month_key(b.month),
                "budgeted": float(b.amount),
                "spent": round(spent, 2),
                "utilization_pct": round(calculate_budget_utilization(spent, float(b.amount)), 1),
            }
        )
    return sorted(result, key=lambda r: r["month"], reverse=True)


@router.get("/overview")
async def get_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Top-line numbers for the dashboard: all-time balance, this month's activity, active alerts."""
    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()

    total_income = sum(float(t.amount) for t in transactions if t.transaction_type == "income")
    total_expense = sum(float(t.amount) for t in transactions if t.transaction_type == "expense")

    now = datetime.now(timezone.utc)
    this_month = [t for t in transactions if t.transaction_date.year == now.year and t.transaction_date.month == now.month]
    month_income = sum(float(t.amount) for t in this_month if t.transaction_type == "income")
    month_expense = sum(float(t.amount) for t in this_month if t.transaction_type == "expense")

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
        "transaction_count": len(transactions),
    }
