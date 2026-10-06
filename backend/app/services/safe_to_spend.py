from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Account, Bill, RecurringTransaction, Transaction, User
from app.services.dashboard import month_start, next_month

ZERO = Decimal("0")

def calculate_safe_to_spend(db: Session, user: User, today: date) -> dict:
    # 1. Total liquid balance (Bank, Cash, Wallet only - exclude credit cards, investments, properties)
    liquid_accs = db.scalars(select(Account).where(
        Account.user_id == user.id,
        Account.archived.is_(False),
        Account.kind.in_(["bank", "cash", "wallet"])
    )).all()
    liquid_acc_ids = {a.id for a in liquid_accs}

    opening = sum((a.opening_balance for a in liquid_accs), ZERO)
    income_sum = Decimal(db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user.id,
        Transaction.type == "income",
        Transaction.account_id.in_(liquid_acc_ids) if liquid_acc_ids else False
    )) or 0)
    expense_sum = Decimal(db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user.id,
        Transaction.type == "expense",
        Transaction.account_id.in_(liquid_acc_ids) if liquid_acc_ids else False
    )) or 0)
    current_liquid_balance = max(ZERO, opening + income_sum - expense_sum)

    # 2. Upcoming unpaid bills between today and the end of the month
    m_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    bills = db.scalars(select(Bill).where(
        Bill.user_id == user.id,
        Bill.active.is_(True),
        Bill.paid.is_(False),
        Bill.due_date >= today,
        Bill.due_date <= m_end
    )).all()
    upcoming_bills_total = sum((b.amount for b in bills), ZERO)

    # 3. Monthly savings target
    target = user.monthly_savings_target or ZERO

    # 4. Days remaining in current month
    days_left = max(1, (m_end - today).days + 1)

    # 5. Safe to spend
    committed = upcoming_bills_total + target
    available = max(ZERO, current_liquid_balance - committed)

    daily_safe = (available / Decimal(days_left)).quantize(Decimal("0.01"))
    weekly_safe = (daily_safe * Decimal(7)).quantize(Decimal("0.01"))

    return {
        "as_of": today,
        "days_left_in_month": days_left,
        "liquid_balance": current_liquid_balance,
        "upcoming_bills": upcoming_bills_total,
        "savings_target": target,
        "committed_total": committed,
        "safe_to_spend_total": available,
        "safe_to_spend_daily": daily_safe,
        "safe_to_spend_weekly": weekly_safe,
        "currency": user.currency,
        "accounts_included": [a.name for a in liquid_accs],
    }

def calculate_cashflow_timeline(db: Session, user: User, today: date, days_ahead: int = 60) -> dict:
    """Project cash balance day-by-day over the next N days based on scheduled income and commitments."""
    liquid = calculate_safe_to_spend(db, user, today)["liquid_balance"]

    # Calculate average daily spending from past 30 days
    thirty_days_ago = today - timedelta(days=30)
    past_spend = Decimal(db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user.id,
        Transaction.type == "expense",
        Transaction.date >= thirty_days_ago,
        Transaction.date <= today
    )) or 0)
    avg_daily_spend = (past_spend / Decimal(30)).quantize(Decimal("0.01"))

    # Active repeating bills
    active_bills = db.scalars(select(Bill).where(Bill.user_id == user.id, Bill.active.is_(True))).all()

    points = []
    running_balance = liquid

    for i in range(days_ahead):
        d = today + timedelta(days=i)
        inc_today = ZERO
        bill_today = ZERO

        # Check if user monthly income lands (e.g. 1st of month)
        if d.day == 1 and user.monthly_income and i > 0:
            inc_today += Decimal(user.monthly_income)

        # Check bills due on this day
        for b in active_bills:
            if b.due_date == d:
                bill_today += Decimal(b.amount)
            elif b.auto_repeat and b.anchor_day == d.day and d > b.due_date:
                bill_today += Decimal(b.amount)

        # Apply daily expenditure
        daily_expense = bill_today + (avg_daily_spend if i > 0 else ZERO)
        running_balance = running_balance + inc_today - daily_expense

        points.append({
            "date": d.isoformat(),
            "label": d.strftime("%d %b"),
            "projected_balance": float(running_balance),
            "expected_income": float(inc_today),
            "bills_due": float(bill_today),
            "discretionary_spend": float(avg_daily_spend if i > 0 else 0),
        })

    return {
        "starting_balance": float(liquid),
        "avg_daily_spend": float(avg_daily_spend),
        "days_ahead": days_ahead,
        "currency": user.currency,
        "points": points,
    }
