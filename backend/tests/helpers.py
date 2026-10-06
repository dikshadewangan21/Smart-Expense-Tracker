from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models.core import Category, Transaction, User
from app.services.periods import add_months_anchored


def user_by_email(db, email="a@example.com") -> User:
    return db.scalar(select(User).where(User.email == email))


def cat(db, user, name, kind="expense") -> Category:
    return db.scalar(select(Category).where(Category.user_id == user.id, Category.name == name, Category.kind == kind))


def add_tx(db, user, amount, d, merchant=None, type_="expense", category=None, pm="upi", currency=None, account=None):
    t = Transaction(user_id=user.id, type=type_, amount=Decimal(str(amount)), date=d, merchant=merchant,
                    category_id=category.id if category else None, payment_method=pm,
                    currency=currency or user.currency, account_id=account.id if account else None)
    db.add(t)
    db.flush()
    return t


def monthly(db, user, merchant, amount, last: date, n: int, **kw):
    """n monthly transactions ending at `last` (anchored to its day-of-month)."""
    out = []
    for i in range(n):
        out.append(add_tx(db, user, amount, add_months_anchored(last, -i, last.day), merchant, **kw))
    db.commit()
    return out
