"""Debt and loan tracking: deterministic arithmetic on what the user entered. Not lending or investment advice.

Rules
  * A debt is 'owed' (personal, education, credit_card, borrowed) or 'lent' (money others owe the user).
  * `remaining` changes only through payments (by their principal part) or when the user edits it.
  * A payment has the cash `amount` and the `principal_paid` part that reduced `remaining`; the rest is
    interest/fees. For a debt with an interest rate the default split is interest = remaining * rate / 12 / 100
    (one month's interest, an estimate), principal = amount - interest. The user can override the principal.
  * Payoff projection: month by month, interest = round(balance * rate/1200, 2); balance += interest - EMI,
    the last payment is whatever is left. If the EMI doesn't cover one month's interest there is no payoff
    date and we say so. This assumes you keep paying exactly the EMI on the due day: it is an estimate.
  * Progress = (principal - remaining) / principal, within 0-100%.
"""
from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Bill, Category, Debt, DebtPayment, Transaction
from app.services.income import typical_monthly_income
from app.services.periods import add_months, add_months_anchored

DEBT_KINDS = ("personal", "education", "credit_card", "borrowed", "lent")
CENT = Decimal("0.01")
ZERO = Decimal("0")
MAX_MONTHS = 600


class DebtError(ValueError):
    """A request the data can't support (maps to HTTP 422)."""


def is_owed(debt: Debt) -> bool:
    return debt.kind != "lent"


def interest_estimate(debt: Debt) -> Decimal:
    if not is_owed(debt) or not debt.interest_rate or Decimal(debt.interest_rate) <= 0:
        return ZERO
    return (Decimal(debt.remaining) * Decimal(debt.interest_rate) / 1200).quantize(CENT, ROUND_HALF_UP)


def _due_on(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def next_due(debt: Debt, today: date) -> date | None:
    if debt.due_day is None or Decimal(debt.remaining) <= 0:
        return None
    this = _due_on(today.year, today.month, debt.due_day)
    if this >= today:
        return this
    nxt = add_months(today.replace(day=1), 1)
    return _due_on(nxt.year, nxt.month, debt.due_day)


def simulate_payoff(balance: Decimal, annual_rate: Decimal | None, emi: Decimal | None, first_payment: date,
                    anchor_day: int | None) -> dict:
    """Returns {months, payoff_date, total_interest, total_paid} or {reason}."""
    if balance <= 0:
        return {"months": 0, "payoff_date": None, "total_interest": ZERO, "total_paid": ZERO}
    if not emi or emi <= 0:
        return {"reason": "Add an EMI to see a payoff estimate."}
    r = Decimal(annual_rate or 0) / 1200
    if r > 0 and (balance * r).quantize(CENT, ROUND_HALF_UP) >= emi:
        return {"reason": "The EMI does not cover a month's interest, so the balance would never reach zero."}
    bal, interest_total, paid_total, n = balance, ZERO, ZERO, 0
    while bal > 0 and n < MAX_MONTHS:
        interest = (bal * r).quantize(CENT, ROUND_HALF_UP)
        pay = min(emi, bal + interest)
        bal = bal + interest - pay
        interest_total += interest
        paid_total += pay
        n += 1
    if bal > 0:
        return {"reason": "At this EMI the debt would take more than 50 years to clear."}
    return {"months": n, "payoff_date": add_months_anchored(first_payment, n - 1, anchor_day),
            "total_interest": interest_total, "total_paid": paid_total}


def payments_of(db: Session, debt_id: int) -> list[DebtPayment]:
    return list(db.scalars(select(DebtPayment).where(DebtPayment.debt_id == debt_id)
                           .order_by(DebtPayment.date.desc(), DebtPayment.id.desc())))


def view(db: Session, debt: Debt, today: date, bills: dict[int, str] | None = None, with_payments: bool = False) -> dict:
    principal, remaining = Decimal(debt.principal), Decimal(debt.remaining)
    pays = payments_of(db, debt.id)
    out = {
        "id": debt.id, "name": debt.name, "kind": debt.kind, "direction": "owed" if is_owed(debt) else "lent",
        "principal": principal, "remaining": remaining,
        "interest_rate": debt.interest_rate, "emi": debt.emi, "due_day": debt.due_day, "start_date": debt.start_date,
        "bill_id": debt.bill_id, "bill_name": (bills or {}).get(debt.bill_id) if debt.bill_id else None,
        "paid_off": remaining <= 0,
        "progress_percent": float(max(min((principal - remaining) / principal * 100, Decimal(100)), ZERO)) if principal > 0 else None,
        "principal_paid_total": sum((Decimal(p.principal_paid) for p in pays), ZERO),
        "interest_paid_total": sum((Decimal(p.amount) - Decimal(p.principal_paid) for p in pays), ZERO),
        "payments_count": len(pays), "last_payment_date": pays[0].date if pays else None,
        "next_due_date": None, "days_until_due": None, "payoff": None,
    }
    nd = next_due(debt, today)
    if nd:
        out["next_due_date"], out["days_until_due"] = nd, (nd - today).days
    if is_owed(debt) and remaining > 0:
        first = nd or add_months(today, 1)
        out["payoff"] = simulate_payoff(remaining, debt.interest_rate, debt.emi, first, debt.due_day)
    if with_payments:
        out["payments"] = [{"id": p.id, "date": p.date, "amount": p.amount, "principal_paid": p.principal_paid,
                            "interest_paid": Decimal(p.amount) - Decimal(p.principal_paid),
                            "transaction_id": p.transaction_id} for p in pays]
    return out


def bill_names(db: Session, user_id: int) -> dict[int, str]:
    return {i: n for i, n in db.execute(select(Bill.id, Bill.name).where(Bill.user_id == user_id))}


def list_views(db: Session, user_id: int, today: date, sort: str = "due") -> list[dict]:
    names = bill_names(db, user_id)
    views = [view(db, d, today, names) for d in db.scalars(select(Debt).where(Debt.user_id == user_id).order_by(Debt.id))]
    far = date.max
    key = {"due": lambda v: (v["paid_off"], v["next_due_date"] or far, v["name"].lower()),
           "remaining": lambda v: (v["paid_off"], -v["remaining"], v["name"].lower()),
           "rate": lambda v: (v["paid_off"], -(v["interest_rate"] or ZERO), v["name"].lower()),
           "name": lambda v: (v["name"].lower(),)}[sort]
    return sorted(views, key=key)


def summary(db: Session, user, views: list[dict], today: date) -> dict:
    live = [v for v in views if not v["paid_off"]]
    owed = [v for v in live if v["direction"] == "owed"]
    emi = sum((Decimal(v["emi"]) for v in owed if v["emi"]), ZERO)
    income = typical_monthly_income(db, user, today)
    return {
        "total_owed": sum((v["remaining"] for v in owed), ZERO),
        "total_lent": sum((v["remaining"] for v in live if v["direction"] == "lent"), ZERO),
        "monthly_emi": emi,
        "debt_to_income_percent": float(emi / income * 100) if income and emi > 0 else None,
        "interest_paid_total": sum((v["interest_paid_total"] for v in views), ZERO),
        "active": len(live), "paid_off": len(views) - len(live),
    }


def linked_bill_ids(db: Session, user_id: int) -> frozenset[int]:
    return frozenset(b for (b,) in db.execute(select(Debt.bill_id).where(Debt.user_id == user_id, Debt.bill_id.is_not(None))))


# ---------- payments ----------

def default_split(debt: Debt, amount: Decimal) -> tuple[Decimal, Decimal]:
    """(principal part, estimated one-month interest) for a payment of `amount`."""
    interest = interest_estimate(debt)
    principal = min(max(amount - interest, ZERO), Decimal(debt.remaining)) if interest > 0 else amount
    return principal, interest


def _expense_category(db: Session, user_id: int) -> int | None:
    return db.scalar(select(Category.id).where(Category.user_id == user_id, Category.name == "EMI & Loans", Category.kind == "expense"))


def record_payment(db: Session, user, debt: Debt, *, amount: Decimal, paid_on: date, principal_paid: Decimal | None = None,
                   create_transaction: bool = False, account_id: int | None = None,
                   payment_method: str = "other") -> DebtPayment:
    if amount <= 0:
        raise DebtError("The payment must be more than zero.")
    remaining = Decimal(debt.remaining)
    if remaining <= 0:
        raise DebtError("This debt is already fully paid.")
    if create_transaction and not is_owed(debt):
        raise DebtError("Money you lent being repaid is not income, so it is not recorded as a transaction.")
    if principal_paid is None:
        principal, interest = default_split(debt, amount)
        if principal > remaining or (amount - principal) > interest + CENT:
            raise DebtError("That is more than the remaining balance" + (" plus a month's interest." if interest > 0 else "."))
    else:
        principal = principal_paid
        if principal < 0 or principal > amount:
            raise DebtError("The principal part must be between 0 and the payment amount.")
        if principal > remaining:
            raise DebtError("The principal part is more than the remaining balance.")
    debt.remaining = remaining - principal
    tx_id = None
    if create_transaction:
        tx = Transaction(user_id=user.id, type="expense", amount=amount, currency=user.currency,
                         category_id=_expense_category(db, user.id), merchant=debt.name, date=paid_on,
                         payment_method=payment_method, account_id=account_id, source="debt",
                         notes=f"Payment towards {debt.name}")
        db.add(tx)
        db.flush()
        tx_id = tx.id
    p = DebtPayment(debt_id=debt.id, amount=amount, principal_paid=principal, date=paid_on, transaction_id=tx_id)
    db.add(p)
    db.flush()
    return p


def record_for_bill(db: Session, debt: Debt, *, amount: Decimal, paid_on: date, transaction_id: int | None) -> DebtPayment | None:
    """Called when the linked bill is paid. Never fails the bill payment: a paid-off debt is skipped and an
    over-large payment is clamped to the balance."""
    remaining = Decimal(debt.remaining)
    if remaining <= 0 or not is_owed(debt):
        return None
    principal, _ = default_split(debt, amount)
    principal = min(principal, remaining)
    debt.remaining = remaining - principal
    p = DebtPayment(debt_id=debt.id, amount=amount, principal_paid=principal, date=paid_on, transaction_id=transaction_id)
    db.add(p)
    db.flush()
    return p


def remove_payment(db: Session, debt: Debt, p: DebtPayment) -> None:
    """Undo a payment: the principal part goes back onto `remaining`. A transaction created with it is kept."""
    debt.remaining = Decimal(debt.remaining) + Decimal(p.principal_paid)
    db.delete(p)
