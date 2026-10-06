from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import Account, AccountValuation, AuditLog, User
from app.schemas.phase4 import AccountUpdate, ValuationIn
from app.services import networth as svc

router = APIRouter(tags=["net-worth"])


def _acc(db: Session, user: User, account_id: int) -> Account:
    a = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if a is None:
        raise HTTPException(404, "Account not found.")
    return a


@router.get("/net-worth", summary="Assets, liabilities, net worth, a monthly trend and what changed since a month ago")
def net_worth(months: int = Query(12, ge=1, le=60), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.build(db, user, user_today(user), months)


@router.put("/accounts/{account_id}", summary="Rename, change type or opening balance, archive or restore an account")
def update_account(account_id: int, body: AccountUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _acc(db, user, account_id)
    for f in ("name", "kind", "opening_balance", "archived"):
        v = getattr(body, f)
        if v is not None:
            setattr(a, f, v)
    db.add(AuditLog(user_id=user.id, action="account_update", detail=f"id={a.id}"))
    db.commit()
    return {"id": a.id, "name": a.name, "kind": a.kind, "opening_balance": a.opening_balance, "archived": a.archived}


def _val_out(v: AccountValuation) -> dict:
    return {"id": v.id, "date": v.date, "value": v.value, "note": v.note}


@router.get("/accounts/{account_id}/valuations", summary="Dated values for an account (investments, property)")
def list_valuations(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _acc(db, user, account_id)
    rows = db.scalars(select(AccountValuation).where(AccountValuation.account_id == a.id).order_by(AccountValuation.date.desc()))
    return [_val_out(v) for v in rows]


@router.post("/accounts/{account_id}/valuations", status_code=201,
             summary="Record what the account is worth at the end of a date (replaces any entry for that date)")
def set_valuation(account_id: int, body: ValuationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _acc(db, user, account_id)
    if body.date > user_today(user):
        raise HTTPException(422, "The date can't be in the future.")
    v = db.scalar(select(AccountValuation).where(AccountValuation.account_id == a.id, AccountValuation.date == body.date))
    if v is None:
        v = AccountValuation(account_id=a.id, date=body.date, value=body.value, note=body.note)
        db.add(v)
    else:
        v.value, v.note = body.value, body.note
    db.commit()
    return _val_out(v)


@router.delete("/accounts/{account_id}/valuations/{valuation_id}", status_code=204)
def delete_valuation(account_id: int, valuation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _acc(db, user, account_id)
    v = db.scalar(select(AccountValuation).where(AccountValuation.id == valuation_id, AccountValuation.account_id == a.id))
    if v is None:
        raise HTTPException(404, "Valuation not found.")
    db.delete(v)
    db.commit()
