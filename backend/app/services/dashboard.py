"""Dashboard calculations. Pure deterministic functions over stored data.

Conventions:
- Transfers are excluded from income/expense totals.
- Every number returned is computed here from the database; nothing is hardcoded.
- A metric with no underlying data is returned as None (never a made-up default).
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Account, Budget, BudgetCategory, Category, Debt, Goal, Transaction
from app.services import analytics as analytics_svc
from app.services import bills as bills_svc
from app.services import debts as debts_svc
from app.services import goals as goals_svc
from app.services import networth as networth_svc
from app.services import recurring as recurring_svc
from app.services.periods import resolve_period

ZERO = Decimal("0")
MONTHLY_FACTOR = {"weekly": Decimal("52") / 12, "monthly": Decimal(1),
                  "quarterly": Decimal(1) / 3, "yearly": Decimal(1) / 12}


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def prev_month(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def _sum(db: Session, user_id: int, tx_type: str, start: date | None = None, end: date | None = None,
         category_id: int | None = None) -> Decimal:
    q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user_id, Transaction.type == tx_type)
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date < end)
    if category_id is not None:
        q = q.where(Transaction.category_id == category_id)
    return Decimal(db.scalar(q))


def total_balance(db: Session, user_id: int) -> Decimal:
    opening = Decimal(db.scalar(select(func.coalesce(func.sum(Account.opening_balance), 0)).where(
        Account.user_id == user_id, Account.archived.is_(False))))
    return opening + _sum(db, user_id, "income") - _sum(db, user_id, "expense")


def spend_by_category(db: Session, user_id: int, start: date, end: date) -> list[dict]:
    rows = db.execute(
        select(Transaction.category_id, Category.name, func.sum(Transaction.amount))
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id, Transaction.type == "expense",
               Transaction.date >= start, Transaction.date < end)
        .group_by(Transaction.category_id, Category.name)
        .order_by(func.sum(Transaction.amount).desc())).all()
    return [{"category_id": cid, "category": name or "Uncategorized", "amount": Decimal(amt)}
            for cid, name, amt in rows]


def monthly_trend(db: Session, user_id: int, today: date, months: int = 6) -> list[dict]:
    out, m = [], month_start(today)
    starts = []
    for _ in range(months):
        starts.append(m)
        m = prev_month(m)
    for s in reversed(starts):
        e = next_month(s)
        out.append({"month": s.strftime("%Y-%m"), "income": _sum(db, user_id, "income", s, e),
                    "expenses": _sum(db, user_id, "expense", s, e)})
    return out


def budget_status(db: Session, user_id: int, month: date) -> dict | None:
    budget = db.scalar(select(Budget).where(Budget.user_id == user_id, Budget.month == month)
                       .order_by(Budget.id.desc()))
    if budget is None:
        return None
    end = next_month(month)
    lines = []
    rows = db.execute(select(BudgetCategory, Category.name).join(Category, Category.id == BudgetCategory.category_id)
                      .where(BudgetCategory.budget_id == budget.id)).all()
    for bc, name in rows:
        used = _sum(db, user_id, "expense", month, end, category_id=bc.category_id)
        limit = Decimal(bc.limit_amount)
        lines.append({"category": name, "limit": limit, "used": used, "remaining": limit - used,
                      "percent_used": float(used / limit * 100) if limit > 0 else None})
    total_used = _sum(db, user_id, "expense", month, end)
    total_limit = Decimal(budget.total_limit)
    return {"name": budget.name, "total_limit": total_limit, "total_used": total_used,
            "remaining": total_limit - total_used, "categories": lines}


def monthly_recurring_cost(db: Session, user_id: int, exclude_debt_bills: bool = False) -> Decimal:
    """Monthly cost of repeating bills plus confirmed recurring payments (see bills.monthly_commitments).
    For the health score, bills that pay a tracked debt are left out: the debt-burden component already counts that EMI."""
    skip = debts_svc.linked_bill_ids(db, user_id) if exclude_debt_bills else frozenset()
    return bills_svc.monthly_commitments(db, user_id, skip)["total"]


def goals_summary(db: Session, user, today: date) -> list[dict]:
    out = []
    for v in goals_svc.list_views(db, user.id, today):
        out.append({"id": v["id"], "name": v["name"], "target": v["target_amount"], "current": v["current_amount"],
                    "remaining": v["remaining"], "percent": v["percent"], "target_date": v["target_date"],
                    "status": v["status"], "required_monthly": v["required_monthly"], "on_track": v["on_track"],
                    "estimated_completion": v["estimated_completion"]})
    return out


def net_worth(db: Session, user, today: date) -> dict:
    """Assets, liabilities and net worth from the same service as /net-worth (see services/networth.py)."""
    return networth_svc.totals(db, user, today)


def health_score(db: Session, user_id: int, month: date, monthly_income_declared: Decimal | None) -> dict:
    """Transparent score. Each component has points/max and a plain-language reason.
    Only components with enough data are scored; the total is rescaled to 100 over the scored max.
    """
    end = next_month(month)
    income = _sum(db, user_id, "income", month, end) or (monthly_income_declared or ZERO)
    expenses = _sum(db, user_id, "expense", month, end)
    comps = []

    if income > 0:
        rate = (income - expenses) / income
        pts = max(0.0, min(float(rate) / 0.20, 1.0)) * 30  # 20%+ savings rate earns full 30 pts
        comps.append({"key": "savings_rate", "label": "Savings rate", "points": round(pts, 1), "max": 30,
                      "value": round(float(rate) * 100, 1),
                      "reason": f"You kept {rate * 100:.1f}% of income this month; 20% or more earns full points."})

    bs = budget_status(db, user_id, month)
    if bs and bs["categories"]:
        within = sum(1 for c in bs["categories"] if c["used"] <= c["limit"])
        frac = within / len(bs["categories"])
        comps.append({"key": "budget_adherence", "label": "Budget adherence", "points": round(frac * 25, 1),
                      "max": 25, "value": round(frac * 100, 1),
                      "reason": f"{within} of {len(bs['categories'])} category budgets are within their limit."})

    if income > 0:
        load = monthly_recurring_cost(db, user_id, exclude_debt_bills=True) / income
        pts = max(0.0, min(1 - float(load) / 0.5, 1.0)) * 15  # 0% load = 15, 50%+ = 0
        comps.append({"key": "recurring_load", "label": "Recurring-payment load", "points": round(pts, 1),
                      "max": 15, "value": round(float(load) * 100, 1),
                      "reason": f"Recurring payments take {load * 100:.1f}% of income; lower is better."})

        emi = Decimal(db.scalar(select(func.coalesce(func.sum(Debt.emi), 0)).where(
            Debt.user_id == user_id, Debt.kind != "lent", Debt.remaining > 0)))
        ratio = emi / income
        pts = max(0.0, min(1 - float(ratio) / 0.4, 1.0)) * 15  # 0% = 15, 40%+ = 0
        comps.append({"key": "debt_burden", "label": "Debt burden", "points": round(pts, 1), "max": 15,
                      "value": round(float(ratio) * 100, 1),
                      "reason": f"Loan EMIs take {ratio * 100:.1f}% of income; lower is better."})

    efs = list(db.scalars(select(Goal).where(Goal.user_id == user_id, Goal.kind == "emergency_fund")))
    ef_target = sum((Decimal(g.target_amount) for g in efs), Decimal(0))
    if efs and ef_target > 0:  # several emergency-fund goals are treated as one pot
        frac = float(min(sum((Decimal(g.current_amount) for g in efs), Decimal(0)) / ef_target, Decimal(1)))
        comps.append({"key": "emergency_fund", "label": "Emergency fund", "points": round(frac * 15, 1),
                      "max": 15, "value": round(frac * 100, 1),
                      "reason": f"Your emergency fund is {frac * 100:.0f}% of its target."})

    max_total = sum(c["max"] for c in comps)
    score = round(sum(c["points"] for c in comps) / max_total * 100) if max_total else None
    return {"score": score, "components": comps,
            "note": None if comps else "Add income and transactions to see your score."}


def health_with_changes(db: Session, user_id: int, month: date, declared_income: Decimal | None) -> dict:
    cur = health_score(db, user_id, month, declared_income)
    prev = health_score(db, user_id, prev_month(month), declared_income)
    prev_by_key = {c["key"]: c for c in prev["components"]}
    for c in cur["components"]:
        p = prev_by_key.get(c["key"])
        c["change_points"] = round(c["points"] - p["points"], 1) if p else None
    cur["previous_score"] = prev["score"]
    cur["score_change"] = (cur["score"] - prev["score"]) if cur["score"] is not None and prev["score"] is not None else None
    return cur


def insights(db: Session, user_id: int, today: date) -> list[str]:
    """Plain facts computed from data. Not LLM output."""
    ms = month_start(today)
    cur = {r["category"]: r["amount"] for r in spend_by_category(db, user_id, ms, next_month(ms))}
    prv = {r["category"]: r["amount"] for r in spend_by_category(db, user_id, prev_month(ms), ms)}
    out = []
    movers = [(c, a, prv[c]) for c, a in cur.items() if prv.get(c, ZERO) > 0 and a != prv[c]]
    if movers:
        c, a, p = max(movers, key=lambda x: abs(x[1] - x[2]) / x[2])
        pct = (a - p) / p * 100
        out.append(f"You spent {abs(pct):.0f}% {'more' if pct > 0 else 'less'} on {c} this month than last month "
                   f"(₹{a:,.0f} vs ₹{p:,.0f}), comparing the full previous month.")
    rec = monthly_recurring_cost(db, user_id)
    if rec > 0:
        out.append(f"Your bills and recurring payments come to about ₹{rec:,.0f}/month.")
    bs = budget_status(db, user_id, ms)
    if bs:
        days_left = monthrange(today.year, today.month)[1] - today.day
        out.append(f"₹{bs['remaining']:,.0f} remains of your ₹{bs['total_limit']:,.0f} budget, with {days_left} days left in the month.")
    return out


def recurring_summary(db: Session, user, today: date) -> dict:
    confirmed = recurring_svc.totals(recurring_svc.list_records(db, user, today, "expense", ("confirmed", "paused")))
    commit = bills_svc.monthly_commitments(db, user.id)
    return {"subscriptions_count": confirmed["count"], "subscriptions_monthly": confirmed["monthly_cost"],
            "subscriptions_annual": confirmed["annual_cost"], "bills_monthly": commit["bills"],
            "total_monthly": commit["total"], "total_annual": (commit["total"] * 12).quantize(Decimal("0.01")),
            "pending_review": len(recurring_svc.detect(db, user, today, "expense"))}


def analytics_summary(db: Session, user, today: date) -> dict:
    start = today.replace(day=1)
    t = analytics_svc.totals(db, user, start, today)
    cats = [c for c in analytics_svc.by_category(db, user, start, today) if c["category_id"] is not None]
    return {"savings_rate": t["savings_rate"], "average_daily_spending": analytics_svc.q2(
        t["expenses"] / analytics_svc.effective_days(start, today, today)),
        "highest_category": cats[0] if cats else None,
        "month_over_month": analytics_svc.month_over_month(db, user, today)}


def build_dashboard(db: Session, user, today: date | None = None) -> dict:
    today = today or date.today()
    ms, me = month_start(today), next_month(month_start(today))
    income, expenses = _sum(db, user.id, "income", ms, me), _sum(db, user.id, "expense", ms, me)
    bs = budget_status(db, user.id, ms)
    nw = net_worth(db, user, today)
    return {
        "as_of": today,
        "currency": user.currency,
        "cards": {
            "total_balance": total_balance(db, user.id),
            "month_income": income,
            "month_expenses": expenses,
            "savings": income - expenses,
            "budget_remaining": bs["remaining"] if bs else None,
            "net_worth": nw["net_worth"],
        },
        "overview": {"income": income, "expenses": expenses, "savings": income - expenses,
                     "net_cash_flow": income - expenses},
        "spending_by_category": spend_by_category(db, user.id, ms, me),
        "monthly_trend": monthly_trend(db, user.id, today),
        "budget_status": bs,
        "upcoming_payments": bills_svc.upcoming(db, user, today, 30),
        "recurring_summary": recurring_summary(db, user, today),
        "analytics_summary": analytics_summary(db, user, today),
        "what_changed": analytics_svc.what_changed(db, user, resolve_period("this_month", today), today),
        "goals": goals_summary(db, user, today),
        "insights": insights(db, user.id, today),
        "financial_health": health_with_changes(db, user.id, ms, user.monthly_income),
        "net_worth_detail": nw,
    }
