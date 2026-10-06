"""Bills, the combined upcoming-payments list, and the money calendar.

Bill model in one paragraph: `due_date` is always the *next unpaid* due date. Paying a repeating
bill records the payment and moves `due_date` forward by exactly one period, so a bill that is
several cycles behind is cleared one cycle per payment. One-time bills (and repeating bills with
auto_repeat off) become `paid`.

A confirmed recurring payment that has the same name as an active bill is treated as the bill
(the bill has an explicit due date), so the same payment is never listed twice.
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.income import typical_monthly_income
from app.models.core import Bill, Category, Transaction
from app.services import recurring as rec_svc
from app.services.categories import merchant_key
from app.services.schedule import monthly_equivalent, occurrences_between, step

BILL_KINDS = ("rent", "electricity", "internet", "phone", "insurance", "emi", "credit_card", "custom")
BILL_FREQUENCIES = ("once", "weekly", "monthly", "quarterly", "yearly")
DEFAULT_REMINDERS = [7, 3, 1, 0]
LARGE_SHARE = Decimal("0.25")  # a scheduled payment is "large" at >= 25% of typical monthly income
ZERO = Decimal("0")
CENT = Decimal("0.01")


def effective_reminders(bill: Bill) -> list[int]:
    return sorted(set(bill.reminder_days), reverse=True) if bill.reminder_days is not None else list(DEFAULT_REMINDERS)


def status_of(bill: Bill, today: date) -> str:
    if not bill.active:
        return "inactive"
    if bill.paid:
        return "paid"
    if bill.due_date < today:
        return "overdue"
    return "due_today" if bill.due_date == today else "upcoming"


def repeats(bill: Bill) -> bool:
    return bill.frequency != "once" and bill.auto_repeat


def view(bill: Bill, today: date, cat_names: dict[int, str]) -> dict:
    amount = Decimal(bill.amount)
    return {
        "id": bill.id, "name": bill.name, "kind": bill.kind, "amount": amount, "category_id": bill.category_id,
        "category": cat_names.get(bill.category_id), "due_date": bill.due_date, "frequency": bill.frequency,
        "auto_repeat": bill.auto_repeat, "notes": bill.notes, "reminder_days": effective_reminders(bill),
        "active": bill.active, "paid": bill.paid, "last_paid": bill.last_paid, "status": status_of(bill, today),
        "days_until": (bill.due_date - today).days,
        "monthly_equivalent": monthly_equivalent(amount, bill.frequency) if bill.frequency != "once" else None,
    }


def category_names(db: Session, user_id: int) -> dict[int, str]:
    return {i: n for i, n in db.execute(select(Category.id, Category.name).where(Category.user_id == user_id))}


def pay(bill: Bill, paid_on: date) -> None:
    """Mark the current cycle paid and move to the next one (or finish a one-time bill)."""
    bill.last_paid = paid_on
    if repeats(bill):
        bill.due_date = step(bill.due_date, bill.frequency, 1, bill.anchor_day)
    else:
        bill.paid = True


def summary(db: Session, user, today: date) -> dict:
    bills = list(db.scalars(select(Bill).where(Bill.user_id == user.id, Bill.active.is_(True), Bill.paid.is_(False))))
    overdue = [b for b in bills if b.due_date < today]
    soon = [b for b in bills if today <= b.due_date <= today + timedelta(days=7)]
    monthly = sum((monthly_equivalent(b.amount, b.frequency) for b in bills if repeats(b)), ZERO)
    return {"overdue_count": len(overdue), "overdue_total": sum((Decimal(b.amount) for b in overdue), ZERO),
            "due_next_7_days_total": sum((Decimal(b.amount) for b in soon), ZERO),
            "monthly_commitment": monthly.quantize(CENT)}


def monthly_commitments(db: Session, user_id: int, exclude_bill_ids: frozenset[int] = frozenset()) -> dict:
    """Monthly cost of everything that repeats: active repeating bills + confirmed recurring expenses
    (a recurring item with a bill's name is counted once, as the bill)."""
    from app.models.core import RecurringTransaction  # local import keeps module import order simple

    bills = list(db.scalars(select(Bill).where(Bill.user_id == user_id, Bill.active.is_(True))))
    bill_keys = {merchant_key(b.name) for b in bills}
    counted = [b for b in bills if b.id not in exclude_bill_ids]
    bills_monthly = sum((monthly_equivalent(b.amount, b.frequency) for b in counted if repeats(b) and not b.paid), ZERO)
    recs = db.scalars(select(RecurringTransaction).where(
        RecurringTransaction.user_id == user_id, RecurringTransaction.type == "expense",
        RecurringTransaction.status == "confirmed"))
    rec_monthly = sum((monthly_equivalent(r.amount, r.frequency) for r in recs if r.merchant_key not in bill_keys), ZERO)
    return {"bills": bills_monthly.quantize(CENT), "recurring": rec_monthly.quantize(CENT),
            "total": (bills_monthly + rec_monthly).quantize(CENT)}


# ---------- schedules ----------

def bill_dates(bill: Bill, today: date, end: date) -> list[date]:
    """Dates a bill needs paying, up to `end`: its current due date (possibly overdue), then the
    repeating schedule from today onward."""
    if bill.paid or not bill.active:
        return []
    dates = [bill.due_date] if bill.due_date <= end else []
    if repeats(bill):
        start = max(bill.due_date + timedelta(days=1), today)
        dates += occurrences_between(bill.due_date, bill.frequency, start, end, bill.anchor_day)
    return dates


def recurring_dates(rec: dict, end: date) -> list[date]:
    if rec["next_expected"] is None or rec["next_expected"] > end:
        return []
    return occurrences_between(rec["next_expected"], rec["frequency"], rec["next_expected"], end, rec["anchor_day"])


def group_for(days_until: int) -> str:
    if days_until < 0:
        return "overdue"
    if days_until == 0:
        return "today"
    if days_until == 1:
        return "tomorrow"
    return "this_week" if days_until <= 7 else "later"


GROUPS = ("overdue", "today", "tomorrow", "this_week", "later")


def upcoming(db: Session, user, today: date, horizon_days: int = 60) -> dict:
    end = today + timedelta(days=horizon_days)
    cats = category_names(db, user.id)
    bills = list(db.scalars(select(Bill).where(Bill.user_id == user.id, Bill.active.is_(True))))
    bill_keys = {merchant_key(b.name) for b in bills}
    items = []
    for b in bills:
        for d in bill_dates(b, today, end):
            items.append({"kind": "bill", "ref_id": b.id, "name": b.name, "amount": Decimal(b.amount), "due_date": d,
                          "days_until": (d - today).days, "category": cats.get(b.category_id),
                          "frequency": b.frequency, "bill_kind": b.kind})
    for r in rec_svc.list_records(db, user, today, "expense", ("confirmed",)):
        if r["merchant_key"] in bill_keys:
            continue
        for d in recurring_dates(r, end):
            items.append({"kind": "recurring", "ref_id": r["id"], "name": r["merchant"], "amount": r["amount"],
                          "due_date": d, "days_until": (d - today).days, "category": r["category"],
                          "frequency": r["frequency"], "bill_kind": None})
    items.sort(key=lambda i: (i["due_date"], i["name"].lower(), i["kind"]))
    for i in items:
        i["group"] = group_for(i["days_until"])
    groups = {g: [i for i in items if i["group"] == g] for g in GROUPS}

    def total(lo, hi):
        return sum((i["amount"] for i in items if lo <= i["days_until"] <= hi), ZERO)

    return {"items": items, "groups": groups, "horizon_days": horizon_days,
            "totals": {"overdue": total(-10 ** 6, -1), "next_7_days": total(0, 7), "next_30_days": total(0, 30)},
            "counts": {g: len(v) for g, v in groups.items()}}


# ---------- calendar ----------

def large_threshold(db: Session, user, today: date) -> Decimal | None:
    """25% of typical monthly income: the average of the last three completed months of recorded
    income, or the income declared at onboarding if there is no history. None if neither exists."""
    ref = typical_monthly_income(db, user, today)
    return (ref * LARGE_SHARE).quantize(CENT) if ref else None


def calendar(db: Session, user, today: date, month: date) -> dict:
    start = month.replace(day=1)
    end = start.replace(day=monthrange(start.year, start.month)[1])
    threshold = large_threshold(db, user, today)
    cats = category_names(db, user.id)
    bills = list(db.scalars(select(Bill).where(Bill.user_id == user.id, Bill.active.is_(True))))
    bill_keys = {merchant_key(b.name) for b in bills}
    recs = [r for r in rec_svc.list_records(db, user, today, "expense", ("confirmed",)) if r["merchant_key"] not in bill_keys]
    rec_keys = {r["merchant_key"] for r in recs}
    income_recs = rec_svc.list_records(db, user, today, "income", ("confirmed",))

    events: dict[date, list[dict]] = {}

    def add(d, **ev):
        ev["large"] = bool(threshold is not None and ev["kind"] != "income" and ev["status"] in ("scheduled", "due_today", "overdue")
                           and ev["amount"] >= threshold)
        events.setdefault(d, []).append(ev)

    # What actually happened this month
    for t in db.scalars(select(Transaction).where(
            Transaction.user_id == user.id, Transaction.currency == user.currency, Transaction.type != "transfer",
            Transaction.date >= start, Transaction.date <= end)):
        name = t.merchant or "Income"
        if t.type == "income":
            add(t.date, kind="income", name=name, amount=Decimal(t.amount), source="transaction", ref_id=t.id,
                status="received" if t.date <= today else "expected")
        else:
            k = merchant_key(t.merchant)
            if k in bill_keys:
                add(t.date, kind="bill", name=name, amount=Decimal(t.amount), source="transaction", ref_id=t.id, status="paid")
            elif k in rec_keys:
                add(t.date, kind="recurring", name=name, amount=Decimal(t.amount), source="transaction", ref_id=t.id, status="paid")

    # What is still expected
    for b in bills:
        for d in bill_dates(b, today, end):
            if start <= d <= end:
                status = "overdue" if d < today else "due_today" if d == today else "scheduled"
                add(d, kind="bill", name=b.name, amount=Decimal(b.amount), source="bill", ref_id=b.id, status=status)
    for r in recs:
        for d in recurring_dates(r, end):
            if start <= d <= end:
                add(d, kind="recurring", name=r["merchant"], amount=r["amount"], source="recurring", ref_id=r["id"],
                    status="due_today" if d == today else "scheduled")
    for r in income_recs:
        for d in recurring_dates(r, end):
            if start <= d <= end:
                add(d, kind="income", name=r["merchant"], amount=r["amount"], source="recurring", ref_id=r["id"], status="expected")

    order = {"income": 0, "bill": 1, "recurring": 2}
    days = []
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        evs = sorted(events.get(d, []), key=lambda e: (order[e["kind"]], -e["amount"], e["name"].lower()))
        days.append({"date": d, "is_today": d == today, "events": evs,
                     "income_total": sum((e["amount"] for e in evs if e["kind"] == "income"), ZERO),
                     "outflow_total": sum((e["amount"] for e in evs if e["kind"] != "income"), ZERO)})

    all_ev = [e for evs in events.values() for e in evs]

    def tot(pred):
        return sum((e["amount"] for e in all_ev if pred(e)), ZERO)

    received, expected = tot(lambda e: e["kind"] == "income" and e["status"] == "received"), tot(lambda e: e["kind"] == "income" and e["status"] == "expected")
    paid = tot(lambda e: e["kind"] != "income" and e["status"] == "paid")
    scheduled = tot(lambda e: e["kind"] != "income" and e["status"] in ("scheduled", "due_today"))
    overdue = tot(lambda e: e["kind"] != "income" and e["status"] == "overdue")
    return {"month": start.strftime("%Y-%m"), "start": start, "end": end, "today": today, "days": days,
            "summary": {"income_received": received, "income_expected": expected, "paid": paid, "scheduled": scheduled,
                        "overdue": overdue, "estimated_net": received + expected - paid - scheduled - overdue,
                        "large_count": sum(1 for e in all_ev if e["large"])},
            "large_threshold": threshold}
