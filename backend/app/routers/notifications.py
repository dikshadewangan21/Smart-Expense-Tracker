from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", summary="Get user notification center alerts and unread count")
def get_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Run evaluation to make sure alerts are current
    svc.evaluate_notifications(db, user, user_today(user))
    return svc.list_notifications(db, user.id)

@router.post("/evaluate", summary="Trigger evaluation of alerts (bills, budgets)")
def evaluate_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = svc.evaluate_notifications(db, user, user_today(user))
    return {"new_alerts_created": count}

@router.patch("/{notification_id}/read", summary="Mark an alert as read")
def mark_notification_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ok = svc.mark_read(db, user.id, notification_id)
    if not ok:
        raise HTTPException(404, "Notification not found.")
    return {"status": "ok"}

@router.post("/read-all", summary="Mark all alerts as read")
def mark_all_notifications_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = svc.mark_all_read(db, user.id)
    return {"marked_read": count}
