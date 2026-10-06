"""Analytics and "What Changed". Deterministic SQL + arithmetic only; no LLM involved.

Rules applied everywhere:
  * transfers are never counted as income or expense
  * only transactions in the user's own currency are summed (no FX conversion exists yet);
    the number left out is reported as `excluded_other_currency`
  * a period that is still running is compared with the *same number of days* of the previous
    period, never with a full previous month
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.money import fmt_money
from app.models.core import Budget, Category, Transaction
from app.services.periods import Period, add_months, month_end

ZERO = Decimal("0")
CENT = Decimal("0.01")


def q2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(CENT, ROUND_HALF_UP)


def pct_change(cur: Decimal, prev: Decimal) -> float | None:
    """Percentage change; None when there is no previous value to compare with."""
    if prev == 0:
        return None
    return round(float((cur - prev) / prev * 100), 1)


def effective_days(start: date, end: date, today: date) -> int:
    """Days in [start, end] that have actually happened (future days do not dilute averages)."""
    last = min(end, today)
    return 0 if start > last else (last - start).days + 1


def _base(user, start: date, end: date, *extra):
    return (Transaction.user_id == user.id, Transaction.currency == user.currency,
            Transaction.type != "transfer", Transaction.date >= start, Transaction.date <= end, *extra)


def totals(db: Session, user, start: date, end: date) -> dict:
    rows = db.execute(select(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0), func.count())
                      .where(*_base(user, start, end)).group_by(Transaction.type)).all()
    by = {t: (Decimal(s), c) for t, s, c in rows}
    income, expenses = by.get("income", (ZERO, 0))[0], by.get("expense", (ZERO, 0))[0]
    return {"income": q2(income), "expenses": q2(expenses), "net_savings": q2(income - expenses),
            "savings_rate": round(float((income - expenses) / income * 100), 1) if income > 0 else None,
            "transaction_count": sum(c for _, c in by.values())}


def excluded_other_currency(db: Session, user, start: date, end: date) -> int:
    return db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.user_id == user.id, Transaction.currency != user.currency, Transaction.type != "transfer",
        Transaction.date >= start, Transaction.date <= end)) or 0


def by_category(db: Session, user, start: date, end: date) -> list[dict]:
    rows = db.execute(
        select(Transaction.category_id, Category.name, Category.essential, func.sum(Transaction.amount), func.count())
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(*_base(user, start, end, Transaction.type == "expense"))
        .group_by(Transaction.category_id, Category.name, Category.essential)
        .order_by(func.sum(Transaction.amount).desc(), Category.name)).all()
    total = sum((Decimal(r[3]) for r in rows), ZERO)
    return [{"category_id": cid, "category": name or "Uncategorized", "essential": ess, "amount": q2(Decimal(amt)),
             "count": cnt, "share": round(float(Decimal(amt) / total * 100), 1) if total else 0.0}
            for cid, name, ess, amt, cnt in rows]


def by_merchant(db: Session, user, start: date, end: date, limit: int = 10) -> dict:
    key = func.lower(func.trim(Transaction.merchant))
    rows = db.execute(
        select(key, func.min(Transaction.merchant), func.sum(Transaction.amount), func.count())
        .where(*_base(user, start, end, Transaction.type == "expense", Transaction.merchant.is_not(None)))
        .group_by(key).order_by(func.sum(Transaction.amount).desc(), key)).all()
    rows = [r for r in rows if r[0]]
    total = sum((Decimal(r[2]) for r in rows), ZERO)
    top = [{"merchant_key": " ".join(k.split()), "merchant": name, "amount": q2(Decimal(a)), "count": c,
            "share": round(float(Decimal(a) / total * 100), 1) if total else 0.0} for k, name, a, c in rows[:limit]]
    other = sum((Decimal(r[2]) for r in rows[limit:]), ZERO)
    no_merchant = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        *_base(user, start, end, Transaction.type == "expense"),
        (Transaction.merchant.is_(None)) | (func.trim(Transaction.merchant) == "")))
    return {"top": top, "other_total": q2(other), "other_count": max(len(rows) - limit, 0),
            "no_merchant_total": q2(Decimal(no_merchant))}


def by_payment_method(db: Session, user, start: date, end: date) -> list[dict]:
    rows = db.execute(
        select(Transaction.payment_method, func.sum(Transaction.amount), func.count())
        .where(*_base(user, start, end, Transaction.type == "expense"))
        .group_by(Transaction.payment_method).order_by(func.sum(Transaction.amount).desc())).all()
    total = sum((Decimal(r[1]) for r in rows), ZERO)
    return [{"payment_method": pm, "amount": q2(Decimal(a)), "count": c,
             "share": round(float(Decimal(a) / total * 100), 1) if total else 0.0} for pm, a, c in rows]


def daily_flows(db: Session, user, start: date, end: date) -> dict[date, dict[str, Decimal]]:
    out: dict[date, dict[str, Decimal]] = {}
    for d, t, s in db.execute(select(Transaction.date, Transaction.type, func.sum(Transaction.amount))
                              .where(*_base(user, start, end)).group_by(Transaction.date, Transaction.type)):
        out.setdefault(d, {"income": ZERO, "expense": ZERO})[t] = Decimal(s)
    return out


def series(flows: dict[date, dict[str, Decimal]], start: date, end: date) -> dict:
    """Daily buckets for spans up to 31 days, monthly buckets otherwise. Empty buckets are included."""
    days = (end - start).days + 1
    buckets: dict[str, dict[str, Decimal]] = {}
    if days <= 31:
        gran = "day"
        for i in range(days):
            buckets[(start + timedelta(days=i)).isoformat()] = {"income": ZERO, "expense": ZERO}
        for d, v in flows.items():
            buckets[d.isoformat()]["income"] += v["income"]
            buckets[d.isoformat()]["expense"] += v["expense"]
    else:
        gran = "month"
        m = start.replace(day=1)
        while m <= end:
            buckets[m.strftime("%Y-%m")] = {"income": ZERO, "expense": ZERO}
            m = add_months(m, 1)
        for d, v in flows.items():
            buckets[d.strftime("%Y-%m")]["income"] += v["income"]
            buckets[d.strftime("%Y-%m")]["expense"] += v["expense"]
    return {"granularity": gran, "points": [
        {"bucket": k, "income": q2(v["income"]), "expenses": q2(v["expense"]), "net": q2(v["income"] - v["expense"])}
        for k, v in buckets.items()]}


def monthly_trend(db: Session, user, end_month: date, months: int = 6) -> list[dict]:
    first = add_months(end_month.replace(day=1), -(months - 1))
    last = month_end(end_month)
    flows = daily_flows(db, user, first, last)
    out, m = [], first
    for _ in range(months):
        key = m.strftime("%Y-%m")
        inc = sum((v["income"] for d, v in flows.items() if d.strftime("%Y-%m") == key), ZERO)
        exp = sum((v["expense"] for d, v in flows.items() if d.strftime("%Y-%m") == key), ZERO)
        out.append({"month": key, "income": q2(inc), "expenses": q2(exp), "savings": q2(inc - exp),
                    "savings_rate": round(float((inc - exp) / inc * 100), 1) if inc > 0 else None})
        m = add_months(m, 1)
    return out


def _compare(db, user, cur: tuple[date, date], prev: tuple[date, date], cur_label: str, prev_label: str) -> dict:
    c, p = totals(db, user, *cur)["expenses"], totals(db, user, *prev)["expenses"]
    return {"current": c, "previous": p, "change": q2(c - p), "change_pct": pct_change(c, p),
            "current_range": [cur[0], cur[1]], "previous_range": [prev[0], prev[1]],
            "current_label": cur_label, "previous_label": prev_label}


def month_over_month(db, user, today: date) -> dict:
    first = today.replace(day=1)
    return _compare(db, user, (first, today), (add_months(first, -1), add_months(today, -1)),
                    "this month so far", "same days last month")


def week_over_week(db, user, today: date) -> dict:
    monday = today - timedelta(days=today.weekday())
    return _compare(db, user, (monday, today), (monday - timedelta(days=7), today - timedelta(days=7)),
                    "this week so far", "same days last week")


def largest_transactions(db: Session, user, start: date, end: date, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(Transaction.id, Transaction.merchant, Transaction.amount, Transaction.date, Category.name)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(*_base(user, start, end, Transaction.type == "expense"))
        .order_by(Transaction.amount.desc(), Transaction.id.desc()).limit(limit)).all()
    return [{"id": i, "merchant": m, "amount": q2(Decimal(a)), "date": d, "category": c or "Uncategorized"}
            for i, m, a, d, c in rows]


def essential_split(cats: list[dict]) -> dict:
    ess = sum((c["amount"] for c in cats if c["category_id"] is not None and c["essential"]), ZERO)
    disc = sum((c["amount"] for c in cats if c["category_id"] is not None and not c["essential"]), ZERO)
    unk = sum((c["amount"] for c in cats if c["category_id"] is None), ZERO)
    total = ess + disc + unk
    classified = ess + disc
    return {"essential": q2(ess), "discretionary": q2(disc), "unclassified": q2(unk),
            "essential_share": round(float(ess / classified * 100), 1) if classified else None,
            "coverage": round(float(classified / total * 100), 1) if total else None,
            "note": ("Some spending has no category, so this split is incomplete."
                     if unk > 0 and total and unk / total > Decimal("0.25") else None)}


def budget_performance(db: Session, user, start: date, end: date) -> list[dict]:
    out, m = [], start.replace(day=1)
    while m <= end:
        b = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.month == m).order_by(Budget.id.desc()))
        if b is not None:
            lo, hi = max(m, start), min(month_end(m), end)
            spent = totals(db, user, lo, hi)["expenses"]
            limit = Decimal(b.total_limit)
            out.append({"month": m.strftime("%Y-%m"), "limit": q2(limit), "spent": spent,
                        "percent_used": round(float(spent / limit * 100), 1) if limit > 0 else None,
                        "partial": lo != m or hi != month_end(m)})
        m = add_months(m, 1)
    return out


def analytics(db: Session, user, period: Period, today: date) -> dict:
    t = totals(db, user, period.start, period.end)
    prev = totals(db, user, period.prev_start, period.prev_end)
    days = effective_days(period.start, period.end, today)
    cats = by_category(db, user, period.start, period.end)
    flows = daily_flows(db, user, period.start, period.end)
    spend_days = {d: v["expense"] for d, v in flows.items() if v["expense"] > 0}
    top_day = max(spend_days.items(), key=lambda kv: (kv[1], kv[0])) if spend_days else None
    categorized = [c for c in cats if c["category_id"] is not None]
    return {
        "period": {"kind": period.kind, "label": period.label, "start": period.start, "end": period.end,
                   "days": period.days, "days_elapsed": days},
        "previous_period": {"label": period.prev_label, "start": period.prev_start, "end": period.prev_end},
        "totals": {**t, "average_daily_spending": q2(t["expenses"] / days) if days else None},
        "previous_totals": prev,
        "changes": {"income": q2(t["income"] - prev["income"]), "expenses": q2(t["expenses"] - prev["expenses"]),
                    "income_pct": pct_change(t["income"], prev["income"]),
                    "expenses_pct": pct_change(t["expenses"], prev["expenses"])},
        "by_category": cats,
        "by_merchant": by_merchant(db, user, period.start, period.end),
        "by_payment_method": by_payment_method(db, user, period.start, period.end),
        "income_vs_expenses": series(flows, period.start, period.end),
        "monthly_trend": monthly_trend(db, user, min(period.end, today)),
        "month_over_month": month_over_month(db, user, today),
        "week_over_week": week_over_week(db, user, today),
        "highest_category": categorized[0] if categorized else None,
        "highest_spending_day": {"date": top_day[0], "amount": q2(top_day[1])} if top_day else None,
        "largest_transactions": largest_transactions(db, user, period.start, period.end),
        "essential_vs_discretionary": essential_split(cats),
        "budget_performance": budget_performance(db, user, period.start, period.end),
        "excluded_other_currency": excluded_other_currency(db, user, period.start, period.end),
    }


# ---------- What Changed ----------

def _range(a: date, b: date) -> str:
    return f"{a.day} {a:%b}" if a == b else (f"{a.day}–{b.day} {b:%b}" if (a.year, a.month) == (b.year, b.month)
                                            else f"{a.day} {a:%b} – {b.day} {b:%b}")


def what_changed(db: Session, user, period: Period, today: date) -> dict:
    cur = {(c["category_id"], c["category"]): c["amount"] for c in by_category(db, user, period.start, period.end)}
    prv = {(c["category_id"], c["category"]): c["amount"] for c in by_category(db, user, period.prev_start, period.prev_end)}
    cur_t, prv_t = totals(db, user, period.start, period.end), totals(db, user, period.prev_start, period.prev_end)
    cur_e, prv_e = cur_t["expenses"], prv_t["expenses"]
    delta = q2(cur_e - prv_e)
    cc = user.currency

    rows = []
    for key in set(cur) | set(prv):
        c, p = cur.get(key, ZERO), prv.get(key, ZERO)
        if c == p:
            continue
        rows.append({"category_id": key[0], "category": key[1], "current": c, "previous": p, "change": q2(c - p),
                     "change_pct": pct_change(c, p), "is_new": p == 0, "stopped": c == 0})
    inc = sorted([r for r in rows if r["change"] > 0], key=lambda r: (-r["change"], r["category"]))
    dec = sorted([r for r in rows if r["change"] < 0], key=lambda r: (r["change"], r["category"]))
    inc_total = sum((r["change"] for r in inc), ZERO)
    dec_total = sum((-r["change"] for r in dec), ZERO)
    for r in inc:
        r["share_of_increase"] = round(float(r["change"] / inc_total * 100), 1) if inc_total else None
    for r in dec:
        r["share_of_decrease"] = round(float(-r["change"] / dec_total * 100), 1) if dec_total else None

    comparable = prv_e > 0
    note = f"{_range(period.start, min(period.end, today))} compared with {_range(period.prev_start, period.prev_end)}"
    if not comparable:
        headline = f"There is no spending recorded in {period.prev_label} to compare with."
    elif delta > 0:
        headline = f"Your spending increased by {fmt_money(delta, cc)} compared with {period.prev_label}."
    elif delta < 0:
        headline = f"Your spending decreased by {fmt_money(-delta, cc)} compared with {period.prev_label}."
    else:
        headline = f"Your spending is unchanged compared with {period.prev_label}."

    drivers_sentence = None
    if comparable and delta != 0:
        side = inc if delta > 0 else dec
        side_total = inc_total if delta > 0 else dec_total
        picked, run = [], ZERO
        for r in side:
            picked.append(r)
            run += abs(r["change"])
            if side_total and run / side_total >= Decimal("0.6"):
                break
        if picked:
            names = [r["category"] for r in picked]
            joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
            verb = "increase" if delta > 0 else "decrease"
            drivers_sentence = f"Most of the {verb} came from {joined}."

    return {
        "period": {"kind": period.kind, "label": period.label, "start": period.start, "end": period.end},
        "previous_period": {"label": period.prev_label, "start": period.prev_start, "end": period.prev_end},
        "comparison_note": note, "comparable": comparable,
        "spending": {"current": cur_e, "previous": prv_e, "change": delta, "change_pct": pct_change(cur_e, prv_e)},
        "income": {"current": cur_t["income"], "previous": prv_t["income"], "change": q2(cur_t["income"] - prv_t["income"]),
                   "change_pct": pct_change(cur_t["income"], prv_t["income"])},
        "increases": inc, "decreases": dec, "headline": headline, "drivers_sentence": drivers_sentence,
    }
