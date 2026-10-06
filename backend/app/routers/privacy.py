import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import verify_password
from app.db.session import get_db
from app.models.core import (
    Account, AuditLog, Bill, Budget, Category, Debt, Goal,
    Notification, RecurringTransaction, Transaction, User
)

router = APIRouter(prefix="/privacy", tags=["privacy"])

class DeleteAccountIn(BaseModel):
    password: str

def _json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

@router.get("/export/csv", summary="Export all transactions as CSV")
def export_transactions_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txs = db.scalars(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.date.desc(), Transaction.id.desc())
    ).all()

    cats = {c.id: c.name for c in db.scalars(select(Category).where(Category.user_id == user.id))}
    accounts = {a.id: a.name for a in db.scalars(select(Account).where(Account.user_id == user.id))}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Date", "Type", "Amount", "Currency", "Merchant",
        "Category", "Payment Method", "Account", "Notes", "Recurring", "Source"
    ])

    for t in txs:
        writer.writerow([
            t.id,
            t.date.isoformat(),
            t.type,
            f"{t.amount:.2f}",
            t.currency,
            t.merchant or "",
            cats.get(t.category_id, ""),
            t.payment_method,
            accounts.get(t.account_id, ""),
            t.notes or "",
            "yes" if t.is_recurring else "no",
            t.source,
        ])

    output.seek(0)
    filename = f"transactions_{user.email}_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/json", summary="Complete data takeout (GDPR dump) of all user data in JSON")
def export_takeout_json(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txs = db.scalars(select(Transaction).where(Transaction.user_id == user.id)).all()
    accounts = db.scalars(select(Account).where(Account.user_id == user.id)).all()
    cats = db.scalars(select(Category).where(Category.user_id == user.id)).all()
    bills = db.scalars(select(Bill).where(Bill.user_id == user.id)).all()
    recurring = db.scalars(select(RecurringTransaction).where(RecurringTransaction.user_id == user.id)).all()
    goals = db.scalars(select(Goal).where(Goal.user_id == user.id)).all()
    debts = db.scalars(select(Debt).where(Debt.user_id == user.id)).all()
    budgets = db.scalars(select(Budget).where(Budget.user_id == user.id)).all()

    takeout = {
        "exported_at": datetime.now().isoformat(),
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "currency": user.currency,
            "timezone": user.timezone,
            "monthly_income": user.monthly_income,
            "monthly_savings_target": user.monthly_savings_target,
            "budgeting_style": user.budgeting_style,
        },
        "accounts": [{"id": a.id, "name": a.name, "kind": a.kind, "opening_balance": a.opening_balance} for a in accounts],
        "categories": [{"id": c.id, "name": c.name, "kind": c.kind, "essential": c.essential} for c in cats],
        "transactions": [{
            "id": t.id, "date": t.date, "type": t.type, "amount": t.amount, "merchant": t.merchant,
            "category_id": t.category_id, "payment_method": t.payment_method, "notes": t.notes
        } for t in txs],
        "bills": [{"id": b.id, "name": b.name, "amount": b.amount, "due_date": b.due_date, "frequency": b.frequency} for b in bills],
        "recurring": [{"id": r.id, "merchant": r.merchant, "amount": r.amount, "frequency": r.frequency} for r in recurring],
        "goals": [{"id": g.id, "name": g.name, "target_amount": g.target_amount, "current_amount": g.current_amount} for g in goals],
        "debts": [{"id": d.id, "name": d.name, "principal": d.principal, "remaining": d.remaining, "emi": d.emi} for d in debts],
        "budgets": [{"id": bg.id, "month": bg.month, "total_limit": bg.total_limit} for bg in budgets],
    }

    dump_str = json.dumps(takeout, default=_json_serial, indent=2)
    filename = f"takeout_{user.email}_{date.today().isoformat()}.json"
    return Response(
        content=dump_str,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/audit-logs", summary="Get user security and action audit logs")
def get_audit_logs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.id.desc()).limit(100)).all()
    return [{
        "id": a.id,
        "action": a.action,
        "detail": a.detail,
        "created_at": a.created_at,
    } for a in rows]

@router.post("/delete-account", status_code=204, summary="Permanently delete user account and all personal financial records")
def delete_account(
    body: DeleteAccountIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect password. Account deletion aborted.")

    db.add(AuditLog(user_id=None, action="account_deleted", detail=f"email={user.email}"))
    db.delete(user)
    db.commit()
    response.delete_cookie("refresh_token", path="/api/auth")
