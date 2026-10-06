"""Recurring payments (detection, confirmation) and the Subscriptions view."""
from dataclasses import asdict
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import AuditLog, Category, RecurringTransaction, User
from app.schemas.recurring import (CandidateOut, ConfirmIn, FlowType, IgnoreIn, RecurringIn, RecurringList,
                                   RecurringOut, RecurringUpdate)
from app.services import recurring as svc
from app.services.categories import merchant_key

router = APIRouter(tags=["recurring"])


def _check_category(db: Session, user: User, category_id: int | None, tx_type: str) -> None:
    if category_id is None:
        return
    cat = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
    if cat is None:
        raise HTTPException(422, "That category doesn't exist.")
    if cat.kind != tx_type:
        raise HTTPException(422, f"That category is for {cat.kind}, not {tx_type}.")


def _get_owned(db: Session, user: User, rec_id: int) -> RecurringTransaction:
    rec = db.scalar(select(RecurringTransaction).where(RecurringTransaction.id == rec_id,
                                                       RecurringTransaction.user_id == user.id))
    if rec is None:
        raise HTTPException(404, "Recurring payment not found.")
    return rec


def _one(db: Session, user: User, rec: RecurringTransaction) -> dict:
    today = user_today(user)
    cats = {cid: n for cid, n in db.execute(select(Category.id, Category.name).where(Category.user_id == user.id))}
    return svc.view(rec, today, svc.latest_dates(db, user.id, rec.type, today), cats)


@router.get("/recurring", response_model=RecurringList, summary="Confirmed recurring payments with monthly and annual totals")
def list_recurring(type: FlowType = "expense", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = svc.list_records(db, user, user_today(user), type, ("confirmed", "paused"))
    return {"items": items, "totals": svc.totals(items)}


@router.get("/recurring/ignored", response_model=list[RecurringOut], summary="Patterns the user chose to ignore")
def list_ignored(type: FlowType = "expense", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_records(db, user, user_today(user), type, ("ignored",))


@router.get("/recurring/candidates", response_model=list[CandidateOut],
            summary="Detected recurring patterns awaiting review (confidence >= 0.70; include_uncertain adds 0.40-0.70)")
def candidates(type: FlowType = "expense", include_uncertain: bool = False,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{**asdict(c), "suggested": c.suggested} for c in svc.detect(db, user, user_today(user), type, include_uncertain)]


@router.post("/recurring/confirm", response_model=RecurringOut, status_code=201,
             summary="Turn a detected pattern into a confirmed recurring payment (optionally correcting it)")
def confirm(body: ConfirmIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = user_today(user)
    cand = next((c for c in svc.detect(db, user, today, body.type, include_uncertain=True)
                 if c.merchant_key == merchant_key(body.merchant_key)), None)
    if cand is None:
        raise HTTPException(404, "That pattern is no longer detected, or is already being tracked.")
    _check_category(db, user, body.category_id, body.type)
    rec = svc.record_from_candidate(user.id, cand, "confirmed", frequency=body.frequency, category_id=body.category_id,
                                    amount=body.amount, merchant=body.merchant)
    db.add(rec)
    db.add(AuditLog(user_id=user.id, action="recurring_confirm", detail=cand.merchant_key[:200]))
    db.commit()
    return _one(db, user, rec)


@router.post("/recurring/ignore", response_model=RecurringOut, status_code=201,
             summary="Stop suggesting a detected pattern (delete the record to un-ignore)")
def ignore(body: IgnoreIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = user_today(user)
    cand = next((c for c in svc.detect(db, user, today, body.type, include_uncertain=True)
                 if c.merchant_key == merchant_key(body.merchant_key)), None)
    if cand is None:
        raise HTTPException(404, "That pattern is no longer detected, or is already being tracked.")
    rec = svc.record_from_candidate(user.id, cand, "ignored")
    db.add(rec)
    db.commit()
    return _one(db, user, rec)


@router.post("/recurring", response_model=RecurringOut, status_code=201, summary="Add a recurring payment manually")
def create_manual(body: RecurringIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_category(db, user, body.category_id, body.type)
    key = merchant_key(body.merchant)
    if db.scalar(select(RecurringTransaction.id).where(
            RecurringTransaction.user_id == user.id, RecurringTransaction.type == body.type,
            RecurringTransaction.merchant_key == key)):
        raise HTTPException(409, "You are already tracking (or ignoring) a recurring payment with that name.")
    anchor = None if body.frequency in ("weekly", "biweekly") else body.next_date.day
    rec = RecurringTransaction(
        user_id=user.id, type=body.type, merchant=body.merchant, merchant_key=key, amount=body.amount,
        frequency=body.frequency, category_id=body.category_id, anchor_day=anchor, reminder=body.reminder,
        last_date=svc.prior_step(body.next_date, body.frequency, anchor), status="confirmed", source="manual")
    db.add(rec)
    db.commit()
    return _one(db, user, rec)


@router.put("/recurring/{rec_id}", response_model=RecurringOut,
            summary="Edit amount, frequency, category, name, reminder, or pause/resume")
def update(rec_id: int, body: RecurringUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = _get_owned(db, user, rec_id)
    if rec.status == "ignored":
        raise HTTPException(409, "This pattern is ignored. Remove it from the ignored list to track it again.")
    sent = body.model_fields_set
    if "category_id" in sent:
        _check_category(db, user, body.category_id, rec.type)
        rec.category_id = body.category_id
    if body.merchant is not None:
        rec.merchant = body.merchant  # display name only; matching key is unchanged
    if body.amount is not None:
        rec.amount = body.amount
    if body.frequency is not None and body.frequency != rec.frequency:
        rec.frequency = body.frequency
        rec.anchor_day = None if body.frequency in ("weekly", "biweekly") else (rec.anchor_day or (rec.last_date.day if rec.last_date else None))
    if body.reminder is not None:
        rec.reminder = body.reminder
    if body.status is not None:
        rec.status = body.status
    db.commit()
    return _one(db, user, rec)


@router.delete("/recurring/{rec_id}", status_code=204,
               summary="Delete a record. Deleting an ignored record lets the pattern be suggested again")
def delete(rec_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = _get_owned(db, user, rec_id)
    db.add(AuditLog(user_id=user.id, action="recurring_delete", detail=f"{rec.status}:{rec.merchant_key}"[:200]))
    db.delete(rec)
    db.commit()


@router.get("/subscriptions", summary="Subscriptions view: confirmed recurring expenses, sortable, with totals")
def subscriptions(sort: Literal["cost", "renewal", "category", "monthly"] = "monthly",
                  order: Literal["asc", "desc"] | None = None,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = svc.list_records(db, user, user_today(user), "expense", ("confirmed", "paused"))
    keyf = {
        "cost": lambda r: r["amount"],
        "monthly": lambda r: r["monthly_equivalent"],
        "renewal": lambda r: r["next_expected"] or date.max,
        "category": lambda r: (r["category"] or "~").lower(),
    }[sort]
    default_desc = sort in ("cost", "monthly")
    desc = default_desc if order is None else order == "desc"
    items.sort(key=lambda r: (r["merchant"].lower()))
    items.sort(key=keyf, reverse=desc)
    return {"items": items, "totals": svc.totals(items), "sort": sort,
            "order": "desc" if desc else "asc",
            "pending_review": len(svc.detect(db, user, user_today(user), "expense"))}
