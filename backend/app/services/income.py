"""Typical monthly income, shared by 'large payment' flags and the debt-to-income ratio."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Transaction

ZERO = Decimal("0")


def typical_monthly_income(db: Session, user, today: date) -> Decimal | None:
    """Average of the last three completed months of recorded income (own currency); falls back to the
    income declared at onboarding when there is no history. None if neither exists."""
    first = today.replace(day=1)
    start = first
    for _ in range(3):
        start = (start - timedelta(days=1)).replace(day=1)
    rows = db.scalars(select(Transaction.amount).where(
        Transaction.user_id == user.id, Transaction.type == "income", Transaction.currency == user.currency,
        Transaction.date >= start, Transaction.date < first))
    total = sum((Decimal(a) for a in rows), ZERO)
    if total > 0:
        return total / 3
    return Decimal(user.monthly_income) if user.monthly_income else None
