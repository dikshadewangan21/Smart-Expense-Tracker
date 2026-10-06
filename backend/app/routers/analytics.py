from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.services import analytics as svc
from app.services.periods import Period, resolve_period

router = APIRouter(tags=["analytics"])
PeriodKind = Literal["this_month", "last_month", "last_3_months", "last_6_months", "this_year", "custom"]


def get_period(period: PeriodKind = "this_month", date_from: date | None = None, date_to: date | None = None,
               user: User = Depends(get_current_user)) -> Period:
    try:
        return resolve_period(period, user_today(user), date_from, date_to)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/analytics", summary="Analytics for a period, with a like-for-like comparison against the previous period")
def get_analytics(p: Period = Depends(get_period), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.analytics(db, user, p, user_today(user))


@router.get("/what-changed", summary="What changed in spending versus the previous equivalent period, by category")
def get_what_changed(p: Period = Depends(get_period), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.what_changed(db, user, p, user_today(user))
