from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models.alert import Alert
from app.db.models.budget import Budget
from app.db.models.transaction import Transaction
from app.utils.helpers import calculate_budget_utilization

# Checked from highest to lowest so only the single highest threshold crossed
# fires per evaluation.
THRESHOLDS = (100, 90, 75)

# Alert lifecycle. "resolved" is distinct from "dismissed": a user dismissed
# an alert they have seen, whereas the system resolved one because the spend
# that triggered it was deleted and the budget is healthy again.
STATUS_ACTIVE = "active"
STATUS_DISMISSED = "dismissed"
STATUS_RESOLVED = "resolved"

# An alert in one of these states has been dealt with and suppresses a re-raise
# at the same threshold. "resolved" is deliberately absent: if the spend comes
# back and crosses the threshold again, that is a genuinely new event.
_SUPPRESSING_STATUSES = (STATUS_ACTIVE, STATUS_DISMISSED)


def _find_budget(
    db: Session, user_id: str, category_id: str, month_of, budget: Budget | None
) -> Budget | None:
    if budget is not None:
        return budget
    # Matched by (year, month) in Python rather than exact DB equality, since
    # callers may pass naive or timezone-aware datetimes.
    candidates = (
        db.query(Budget)
        .filter(Budget.user_id == user_id, Budget.category_id == category_id)
        .all()
    )
    return next(
        (b for b in candidates if b.month.year == month_of.year and b.month.month == month_of.month),
        None,
    )


def _month_spend(db: Session, user_id: str, category_id: str, month_of) -> Decimal:
    expenses = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.category_id == category_id,
            Transaction.transaction_type == "expense",
        )
        .all()
    )
    return sum(
        (
            t.amount
            for t in expenses
            if t.transaction_date.year == month_of.year
            and t.transaction_date.month == month_of.month
        ),
        Decimal("0"),
    )


def reconcile_budget_alerts(
    db: Session, user_id: str, category_id: str, month_of, budget: Budget | None = None
) -> Alert | None:
    """
    Brings one budget's alerts in line with current spend, in both directions:

    - resolves active alerts whose threshold is no longer met, which happens
      when the transactions that pushed the budget over are deleted;
    - raises the single highest newly-crossed threshold.

    Called after both creating and deleting a transaction, so the alerts page
    never disagrees with the budget-vs-actual numbers. Returns the newly raised
    alert, if any.
    """
    budget = _find_budget(db, user_id, category_id, month_of, budget)
    if budget is None:
        return None

    utilization = calculate_budget_utilization(_month_spend(db, user_id, category_id, month_of), budget.amount)

    existing = (
        db.query(Alert).filter(Alert.budget_id == budget.id).all()
    )

    # Step 1: stand down anything the current spend no longer justifies.
    changed = False
    for alert in existing:
        if alert.status != STATUS_ACTIVE:
            continue
        if utilization < int(alert.threshold.rstrip("%")):
            alert.status = STATUS_RESOLVED
            changed = True
    if changed:
        db.commit()

    # Step 2: raise the single highest threshold that is met but not yet
    # recorded. THRESHOLDS is ordered high to low, so skip (not break on) the
    # thresholds above the current utilization -- the first one that IS met is
    # the highest, and exactly one alert is raised per evaluation.
    for threshold in THRESHOLDS:
        if utilization < threshold:
            continue
        label = f"{threshold}%"
        already_raised = any(
            a.threshold == label and a.status in _SUPPRESSING_STATUSES for a in existing
        )
        if already_raised:
            return None
        alert = Alert(
            user_id=user_id,
            budget_id=budget.id,
            category_id=category_id,
            threshold=label,
            utilization=round(float(utilization), 2),
            status=STATUS_ACTIVE,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    return None


# Backwards-compatible alias: the original entry point was create-only, but
# reconciliation is a superset of it, so existing callers keep working.
evaluate_budget_alert = reconcile_budget_alerts
