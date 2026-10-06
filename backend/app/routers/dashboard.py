from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import user_today  # noqa: F401  (re-exported; other routers import it from here)
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.services.dashboard import build_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", summary="Dashboard data computed from the signed-in user's transactions")
def dashboard(as_of: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_dashboard(db, user, as_of or user_today(user))
