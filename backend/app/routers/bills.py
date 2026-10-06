import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import Account, AuditLog, Bill, Category, Debt, Transaction, User
from app.schemas.bills import BillIn, BillList, BillOut, PayIn, PayOut
from app.services import bills as svc
from app.services import debts as debts_svc

router = APIRouter(tags=["bills"])
STATUSES = ("overdue", "due_today", "upcoming", "paid", "inactive")


def _check_category(db: Session, user: User, category_id: int | None) -> None:
    if category_id is None:
        return
    cat = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
    if cat is None:
        raise HTTPException(422, "That category doesn't exist.")
    if cat.kind != "expense":
        raise HTTPException(422, "Bills need an expense category.")


def _get_owned(db: Session, user: User, bill_id: int) -> Bill:
    bill = db.scalar(select(Bill).where(Bill.id == bill_id, Bill.user_id == user.id))
    if bill is None:
        raise HTTPException(404, "Bill not found.")
    return bill


def _anchor(due: date, frequency: str) -> int | None:
    return due.day if frequency in ("monthly", "quarterly", "yearly") else None


@router.get("/bills", response_model=BillList, summary="List bills with computed status and a summary")
def list_bills(status: Literal["overdue", "due_today", "upcoming", "paid", "inactive"] | None = None,
               sort: Literal["due", "amount", "name"] = "due",
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = user_today(user)
    cats = svc.category_names(db, user.id)
    items = [svc.view(b, today, cats) for b in db.scalars(select(Bill).where(Bill.user_id == user.id))]
    if status:
        items = [i for i in items if i["status"] == status]
    else:  # default view: things that still need attention or are scheduled; paid/inactive on request
        items = [i for i in items if i["status"] in ("overdue", "due_today", "upcoming")]
    key = {"due": lambda i: (i["due_date"], i["name"].lower()), "amount": lambda i: (-i["amount"], i["name"].lower()),
           "name": lambda i: i["name"].lower()}[sort]
    items.sort(key=key)
    return {"items": items, "summary": svc.summary(db, user, today)}


@router.post("/bills", response_model=BillOut, status_code=201, summary="Create a bill")
def create_bill(body: BillIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_category(db, user, body.category_id)
    bill = Bill(user_id=user.id, name=body.name, kind=body.kind, amount=body.amount, due_date=body.due_date,
                frequency=body.frequency, anchor_day=_anchor(body.due_date, body.frequency),
                category_id=body.category_id, auto_repeat=body.auto_repeat, notes=body.notes,
                reminder_days=body.reminder_days, active=body.active, paid=False)
    db.add(bill)
    db.commit()
    return svc.view(bill, user_today(user), svc.category_names(db, user.id))


@router.get("/bills/{bill_id}", response_model=BillOut)
def get_bill(bill_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.view(_get_owned(db, user, bill_id), user_today(user), svc.category_names(db, user.id))


@router.put("/bills/{bill_id}", response_model=BillOut,
            summary="Replace a bill's editable fields. Changing the due date or frequency reopens a paid bill")
def update_bill(bill_id: int, body: BillIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bill = _get_owned(db, user, bill_id)
    _check_category(db, user, body.category_id)
    if body.due_date != bill.due_date or body.frequency != bill.frequency:
        bill.paid = False
        bill.anchor_day = _anchor(body.due_date, body.frequency)
    for f in ("name", "kind", "amount", "due_date", "frequency", "category_id", "auto_repeat", "notes",
              "reminder_days", "active"):
        setattr(bill, f, getattr(body, f))
    db.commit()
    return svc.view(bill, user_today(user), svc.category_names(db, user.id))


@router.delete("/bills/{bill_id}", status_code=204, summary="Delete a bill (expenses already recorded for it are kept)")
def delete_bill(bill_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bill = _get_owned(db, user, bill_id)
    db.add(AuditLog(user_id=user.id, action="bill_delete", detail=f"id={bill.id}"))
    db.delete(bill)
    db.commit()


@router.post("/bills/{bill_id}/pay", response_model=PayOut,
             summary="Record a payment: optionally creates the expense, then moves a repeating bill to its next due date")
def pay_bill(bill_id: int, body: PayIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bill = _get_owned(db, user, bill_id)
    today = user_today(user)
    if not bill.active:
        raise HTTPException(409, "This bill is switched off. Turn it on before recording a payment.")
    if bill.paid:
        raise HTTPException(409, "This bill is already marked as paid.")
    paid_on = body.paid_on or today
    if paid_on > today:
        raise HTTPException(422, "The payment date can't be in the future.")
    if body.account_id is not None and db.scalar(select(Account.id).where(Account.id == body.account_id, Account.user_id == user.id)) is None:
        raise HTTPException(422, "That account doesn't exist.")
    tx_id = None
    if body.create_transaction:
        tx = Transaction(user_id=user.id, type="expense", amount=body.amount or bill.amount, currency=user.currency,
                         category_id=bill.category_id, merchant=bill.name, date=paid_on,
                         payment_method=body.payment_method, account_id=body.account_id, source="bill",
                         notes=f"Bill payment (due {bill.due_date.isoformat()})")
        db.add(tx)
        db.flush()
        tx_id = tx.id
    svc.pay(bill, paid_on)
    debt = db.scalar(select(Debt).where(Debt.bill_id == bill.id, Debt.user_id == user.id))
    if debt is not None:
        debts_svc.record_for_bill(db, debt, amount=body.amount or bill.amount, paid_on=paid_on, transaction_id=tx_id)
    db.add(AuditLog(user_id=user.id, action="bill_pay", detail=f"id={bill.id}"))
    db.commit()
    return {"bill": svc.view(bill, today, svc.category_names(db, user.id)), "transaction_id": tx_id,
            "debt_id": debt.id if debt else None, "debt_remaining": debt.remaining if debt else None}


@router.get("/upcoming", summary="Bills and confirmed recurring payments in date order, grouped Overdue / Today / Tomorrow / This week / Later")
def upcoming(days: int = Query(60, ge=1, le=365), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.upcoming(db, user, user_today(user), days)


@router.get("/calendar", summary="Money calendar for a month: income, bills, recurring payments and large scheduled payments")
def calendar(month: str | None = Query(None, description="YYYY-MM; defaults to the current month"),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = user_today(user)
    if month is None:
        first = today.replace(day=1)
    else:
        m = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", month)
        if not m or not (2000 <= int(m.group(1)) <= 2100):
            raise HTTPException(422, "Month must look like 2026-10.")
        first = date(int(m.group(1)), int(m.group(2)), 1)
    return svc.calendar(db, user, today, first)
