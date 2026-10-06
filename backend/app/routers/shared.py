from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.services import shared as svc

router = APIRouter(prefix="/shared", tags=["shared"])

class GroupCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="friends", max_length=20)

class MemberAddIn(BaseModel):
    email: str

class GroupExpenseIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str = Field(min_length=1, max_length=200)
    date: date
    paid_by: int
    split_type: str = "equal"
    custom_splits: dict[int, Decimal] | None = None

@router.get("/groups", summary="List groups the current user belongs to")
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_user_groups(db, user.id)

@router.post("/groups", status_code=201, summary="Create a shared finances group")
def create_group(body: GroupCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = svc.create_group(db, user, body.name, body.kind)
    return svc.get_group_detail(db, g.id, user.id)

@router.get("/groups/{group_id}", summary="Get group detail, expenses, balances and settlement steps")
def get_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    detail = svc.get_group_detail(db, group_id, user.id)
    if not detail:
        raise HTTPException(404, "Group not found.")
    return detail

@router.post("/groups/{group_id}/members", summary="Add a member to the group by email")
def add_member(group_id: int, body: MemberAddIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    res = svc.add_member(db, group_id, body.email)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res

@router.post("/groups/{group_id}/expenses", status_code=201, summary="Record a shared group expense")
def add_group_expense(
    group_id: int,
    body: GroupExpenseIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        svc.add_expense(
            db=db,
            group_id=group_id,
            paid_by=body.paid_by,
            amount=body.amount,
            description=body.description,
            exp_date=body.date,
            split_type=body.split_type,
            custom_splits=body.custom_splits,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return svc.get_group_detail(db, group_id, user.id)

@router.delete("/groups/{group_id}/expenses/{expense_id}", status_code=204, summary="Delete a shared group expense")
def delete_group_expense(group_id: int, expense_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ok = svc.delete_expense(db, group_id, expense_id)
    if not ok:
        raise HTTPException(404, "Expense not found.")
