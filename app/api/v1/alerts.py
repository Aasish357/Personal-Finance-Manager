from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.db.models.alert import Alert as DBAlert
from app.db.models.user import User
from app.schemas.alert import Alert

router = APIRouter()


@router.get("/alerts", response_model=List[Alert])
async def get_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Alerts are raised automatically when a transaction pushes a budget's
    utilization past 75/90/100% (see app/utils/budget_alerts.py) -- there is
    no manual "create alert" action in the UI.
    """
    return (
        db.query(DBAlert)
        .filter(DBAlert.user_id == current_user.id)
        .order_by(DBAlert.triggered_at.desc())
        .all()
    )


@router.post("/alerts/{alert_id}/dismiss", response_model=Alert)
async def dismiss_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(DBAlert).filter(DBAlert.id == alert_id, DBAlert.user_id == current_user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "dismissed"
    db.commit()
    db.refresh(alert)
    return alert
