from datetime import date
from decimal import Decimal
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.money import fmt_money
from app.models.core import Bill, Budget, BudgetCategory, Category, Notification, User
from app.services.dashboard import budget_status, month_start

def days_between(target: date, reference: date) -> int:
    return (target - reference).days

def evaluate_notifications(db: Session, user: User, today: date) -> int:
    new_alerts = 0
    cur = user.currency

    # 1. Evaluate Bill reminders and Overdue bills
    bills = db.scalars(select(Bill).where(Bill.user_id == user.id, Bill.active.is_(True), Bill.paid.is_(False))).all()
    for b in bills:
        days = days_between(b.due_date, today)
        reminders = b.reminder_days or [7, 3, 1, 0]

        if days < 0:
            dedupe = f"bill_overdue:{b.id}:{b.due_date.isoformat()}"
            if not _exists(db, user.id, dedupe):
                _create(db, user.id, "bill_overdue", f"Bill '{b.name}' ({fmt_money(b.amount, cur)}) is overdue by {-days} day(s)!", dedupe)
                new_alerts += 1
        elif days in reminders:
            dedupe = f"bill_due:{b.id}:{b.due_date.isoformat()}:{days}"
            if not _exists(db, user.id, dedupe):
                due_label = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days} days")
                _create(db, user.id, "bill_reminder", f"Upcoming bill: '{b.name}' ({fmt_money(b.amount, cur)}) is due {due_label}.", dedupe)
                new_alerts += 1

    # 2. Evaluate Budget thresholds
    m = month_start(today)
    bs = budget_status(db, user.id, m)
    if bs and bs.get("total_limit", 0) > 0:
        pct = float(bs["total_used"] / bs["total_limit"] * 100)
        m_str = m.strftime("%Y-%m")
        if pct >= 100:
            dedupe = f"budget_total:100:{m_str}"
            if not _exists(db, user.id, dedupe):
                _create(db, user.id, "budget_warning", f"You have exceeded 100% of your total budget for {m.strftime('%B')} ({fmt_money(bs['total_used'], cur)} / {fmt_money(bs['total_limit'], cur)}).", dedupe)
                new_alerts += 1
        elif pct >= 80:
            dedupe = f"budget_total:80:{m_str}"
            if not _exists(db, user.id, dedupe):
                _create(db, user.id, "budget_warning", f"Notice: You have used {pct:.0f}% of your monthly budget for {m.strftime('%B')}.", dedupe)
                new_alerts += 1

        for c in bs.get("categories", []):
            cat_pct = c.get("percent_used")
            if cat_pct and cat_pct >= 100:
                dedupe = f"budget_cat:100:{c['category']}:{m_str}"
                if not _exists(db, user.id, dedupe):
                    _create(db, user.id, "budget_warning", f"Category '{c['category']}' has exceeded its budget ({fmt_money(c['used'], cur)} / {fmt_money(c['limit'], cur)}).", dedupe)
                    new_alerts += 1

    db.commit()
    return new_alerts

def _exists(db: Session, user_id: int, dedupe_key: str) -> bool:
    return db.scalar(select(Notification.id).where(Notification.user_id == user_id, Notification.dedupe_key == dedupe_key)) is not None

def _create(db: Session, user_id: int, kind: str, message: str, dedupe_key: str):
    notif = Notification(user_id=user_id, kind=kind, message=message, dedupe_key=dedupe_key, read=False)
    db.add(notif)

def list_notifications(db: Session, user_id: int) -> dict:
    rows = db.scalars(select(Notification).where(Notification.user_id == user_id).order_by(Notification.id.desc()).limit(50)).all()
    unread_count = sum(1 for n in rows if not n.read)
    return {
        "unread_count": unread_count,
        "items": [{
            "id": n.id,
            "kind": n.kind,
            "message": n.message,
            "read": n.read,
            "created_at": n.created_at,
        } for n in rows]
    }

def mark_read(db: Session, user_id: int, notification_id: int) -> bool:
    notif = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if notif:
        notif.read = True
        db.commit()
        return True
    return False

def mark_all_read(db: Session, user_id: int) -> int:
    res = db.execute(update(Notification).where(Notification.user_id == user_id, Notification.read.is_(False)).values(read=True))
    db.commit()
    return res.rowcount
