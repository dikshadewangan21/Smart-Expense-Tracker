from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import AuditLog, Goal, GoalContribution, User
from app.schemas.phase4 import ContributionIn, GoalCreate, GoalUpdate
from app.services import goals as svc

router = APIRouter(tags=["goals"])


def _get_owned(db: Session, user: User, goal_id: int) -> Goal:
    g = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    if g is None:
        raise HTTPException(404, "Goal not found.")
    return g


def _detail(db: Session, g: Goal, today: date) -> dict:
    rows = db.scalars(select(GoalContribution).where(GoalContribution.goal_id == g.id)
                      .order_by(GoalContribution.date.desc(), GoalContribution.id.desc()))
    out = svc.view(db, g, today)
    out["contributions"] = [{"id": c.id, "amount": c.amount, "date": c.date, "note": c.note} for c in rows]
    return out


@router.get("/goals", summary="Savings goals with progress, required monthly saving and an estimated finish date")
def list_goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    views = svc.list_views(db, user.id, user_today(user))
    return {"items": views, "summary": svc.summary(views)}


@router.post("/goals", status_code=201, summary="Create a goal")
def create_goal(body: GoalCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = user_today(user)
    if body.target_date is not None and body.target_date <= today:
        raise HTTPException(422, "The target date must be in the future.")
    g = Goal(user_id=user.id, name=body.name, kind=body.kind, target_amount=body.target_amount,
             current_amount=body.current_amount, target_date=body.target_date)
    db.add(g)
    db.commit()
    return _detail(db, g, today)


@router.get("/goals/{goal_id}", summary="One goal with its contribution history")
def get_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _detail(db, _get_owned(db, user, goal_id), user_today(user))


@router.put("/goals/{goal_id}", summary="Edit a goal's name, kind, target or date (the saved amount changes via contributions)")
def update_goal(goal_id: int, body: GoalUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_owned(db, user, goal_id)
    for f in ("name", "kind", "target_amount"):
        v = getattr(body, f)
        if v is not None:
            setattr(g, f, v)
    if body.clear_target_date:
        g.target_date = None
    elif body.target_date is not None:
        g.target_date = body.target_date
    db.commit()
    return _detail(db, g, user_today(user))


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_owned(db, user, goal_id)
    db.add(AuditLog(user_id=user.id, action="goal_delete", detail=f"id={g.id}"))
    db.delete(g)
    db.commit()


@router.post("/goals/{goal_id}/contributions", status_code=201,
             summary="Add money to a goal (negative amount = withdrawal). Not a transaction: it doesn't count as spending")
def add_contribution(goal_id: int, body: ContributionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_owned(db, user, goal_id)
    today = user_today(user)
    on = body.date or today
    if on > today:
        raise HTTPException(422, "The date can't be in the future.")
    try:
        svc.add_contribution(db, g, body.amount, on, body.note)
    except svc.GoalError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return _detail(db, g, today)


@router.delete("/goals/{goal_id}/contributions/{contribution_id}", summary="Remove a contribution (the saved amount goes back down)")
def remove_contribution(goal_id: int, contribution_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = _get_owned(db, user, goal_id)
    c = db.scalar(select(GoalContribution).where(GoalContribution.id == contribution_id, GoalContribution.goal_id == g.id))
    if c is None:
        raise HTTPException(404, "Contribution not found.")
    try:
        svc.remove_contribution(db, g, c)
    except svc.GoalError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return _detail(db, g, user_today(user))
