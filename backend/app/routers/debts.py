from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import Account, AuditLog, Bill, Debt, DebtPayment, User
from app.schemas.phase4 import DebtCreate, DebtPaymentIn, DebtUpdate
from app.services import debts as svc

router = APIRouter(tags=["debts"])


def _get_owned(db: Session, user: User, debt_id: int) -> Debt:
    d = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id))
    if d is None:
        raise HTTPException(404, "Debt not found.")
    return d


def _check_bill(db: Session, user: User, bill_id: int | None, this_debt: int | None) -> None:
    if bill_id is None:
        return
    if db.scalar(select(Bill.id).where(Bill.id == bill_id, Bill.user_id == user.id)) is None:
        raise HTTPException(422, "That bill doesn't exist.")
    other = db.scalar(select(Debt.id).where(Debt.bill_id == bill_id, Debt.id != (this_debt or 0)))
    if other is not None:
        raise HTTPException(422, "That bill is already linked to another debt.")


def _detail(db: Session, user: User, d: Debt) -> dict:
    return svc.view(db, d, user_today(user), svc.bill_names(db, user.id), with_payments=True)


@router.get("/debts", summary="Debts and loans with progress, payoff estimate and a summary (not financial advice)")
def list_debts(sort: Literal["due", "remaining", "rate", "name"] = "due", user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    today = user_today(user)
    views = svc.list_views(db, user.id, today, sort)
    return {"items": views, "summary": svc.summary(db, user, views, today), "sort": sort}


@router.post("/debts", status_code=201, summary="Add a debt or loan")
def create_debt(body: DebtCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = user_today(user)
    if body.start_date and body.start_date > today:
        raise HTTPException(422, "The start date can't be in the future.")
    _check_bill(db, user, body.bill_id, None)
    d = Debt(user_id=user.id, name=body.name, kind=body.kind, principal=body.principal,
             remaining=body.principal if body.remaining is None else body.remaining, interest_rate=body.interest_rate,
             emi=body.emi, due_day=body.due_day, start_date=body.start_date, bill_id=body.bill_id)
    db.add(d)
    db.commit()
    return _detail(db, user, d)


@router.get("/debts/{debt_id}", summary="One debt with its payment history")
def get_debt(debt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _detail(db, user, _get_owned(db, user, debt_id))


@router.put("/debts/{debt_id}", summary="Edit a debt (set `remaining` to correct the balance)")
def update_debt(debt_id: int, body: DebtUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _get_owned(db, user, debt_id)
    if body.start_date and body.start_date > user_today(user):
        raise HTTPException(422, "The start date can't be in the future.")
    _check_bill(db, user, body.bill_id, d.id)
    for f in ("name", "kind", "principal", "remaining", "interest_rate", "emi", "due_day", "start_date", "bill_id"):
        setattr(d, f, getattr(body, f))
    db.commit()
    return _detail(db, user, d)


@router.delete("/debts/{debt_id}", status_code=204)
def delete_debt(debt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _get_owned(db, user, debt_id)
    db.add(AuditLog(user_id=user.id, action="debt_delete", detail=f"id={d.id}"))
    db.delete(d)
    db.commit()


@router.post("/debts/{debt_id}/payments", status_code=201,
             summary="Record a payment: reduces the balance by its principal part, optionally records the expense")
def add_payment(debt_id: int, body: DebtPaymentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _get_owned(db, user, debt_id)
    today = user_today(user)
    paid_on = body.paid_on or today
    if paid_on > today:
        raise HTTPException(422, "The payment date can't be in the future.")
    if body.account_id is not None and db.scalar(select(Account.id).where(Account.id == body.account_id, Account.user_id == user.id)) is None:
        raise HTTPException(422, "That account doesn't exist.")
    create_tx = body.create_transaction if body.create_transaction is not None else svc.is_owed(d)
    try:
        svc.record_payment(db, user, d, amount=body.amount, paid_on=paid_on, principal_paid=body.principal_paid,
                           create_transaction=create_tx, account_id=body.account_id, payment_method=body.payment_method)
    except svc.DebtError as e:
        raise HTTPException(422, str(e))
    db.add(AuditLog(user_id=user.id, action="debt_payment", detail=f"id={d.id}"))
    db.commit()
    return _detail(db, user, d)


@router.delete("/debts/{debt_id}/payments/{payment_id}",
               summary="Undo a payment: the balance goes back up. A recorded expense is kept; delete it from Transactions if needed")
def delete_payment(debt_id: int, payment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _get_owned(db, user, debt_id)
    p = db.scalar(select(DebtPayment).where(DebtPayment.id == payment_id, DebtPayment.debt_id == d.id))
    if p is None:
        raise HTTPException(404, "Payment not found.")
    svc.remove_payment(db, d, p)
    db.commit()
    return _detail(db, user, d)
