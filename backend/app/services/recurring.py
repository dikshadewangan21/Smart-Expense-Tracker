"""Recurring-payment detection and the confirmed-recurring read model.

Detection is deterministic and computed on demand from transaction history; nothing is
persisted until the user confirms or ignores a candidate.

Algorithm (per merchant, per transaction type):
  1. Collapse same-day entries to one occurrence (so duplicate charges do not create 0-day gaps).
  2. Keep the "core" amounts: within +-25% of the median. Wildly different amounts at the same
     merchant (a one-off big purchase) are not part of the pattern.
  3. Take the day gaps between consecutive core occurrences. The median gap must fall inside one
     frequency window: weekly 6-8, biweekly 12-16, monthly 27-34, quarterly 84-98, yearly 355-375.
     No window -> not recurring (random shopping, daily coffee, ...).
  4. Skip lapsed patterns: if more than 1.75 periods have passed since the last occurrence the
     payment has probably stopped.
  5. Confidence = 0.45*regularity + 0.25*amount_consistency + 0.20*occurrence_score + 0.10*recency
       regularity         share of gaps inside the frequency window
       amount_consistency 1 - (mean absolute deviation / median) / 0.15, floored at 0
       occurrence_score   min(1, occurrences / target)   target: weekly 8, biweekly 6, monthly 6,
                                                         quarterly 4, yearly 3
       recency            1.0 if <=1.25 periods since last, falling linearly to 0.5 at 1.75
     Only two occurrences (possible for yearly only) caps confidence at 0.69, below the threshold.
  6. Candidates >= CONFIDENCE_THRESHOLD (0.70) are suggested. Candidates from 0.40 up are available
     as "possible" patterns that the user may still confirm explicitly. Below 0.40 is discarded.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Bill, Category, RecurringTransaction, Transaction
from app.services.categories import merchant_key
from app.services.schedule import annual_cost, monthly_equivalent, next_after, period_days, step

CONFIDENCE_THRESHOLD = 0.70
CONFIDENCE_FLOOR = 0.40
LOOKBACK_DAYS = 1200  # ~3.3 years, so a yearly payment can show three occurrences
AMOUNT_BAND = 0.25
WINDOWS = {"weekly": (6, 8), "biweekly": (12, 16), "monthly": (27, 34), "quarterly": (84, 98), "yearly": (355, 375)}
TARGET_N = {"weekly": 8, "biweekly": 6, "monthly": 6, "quarterly": 4, "yearly": 3}
CENT = Decimal("0.01")


@dataclass
class Candidate:
    type: str
    merchant_key: str
    merchant: str
    amount: Decimal
    frequency: str
    category_id: int | None
    category: str | None
    last_date: date
    next_expected: date
    occurrences: int
    confidence: float
    anchor_day: int | None
    monthly_equivalent: Decimal
    annual_cost: Decimal
    amount_varies: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def suggested(self) -> bool:
        return self.confidence >= CONFIDENCE_THRESHOLD


def frequency_for_gap(gap: float) -> str | None:
    for freq, (lo, hi) in WINDOWS.items():
        if lo <= gap <= hi:
            return freq
    return None


def _score_group(rows: list[tuple[date, Decimal, int | None, str]], today: date):
    """rows: (date, amount, category_id, merchant display) for ONE merchant. Returns a dict or None."""
    by_date: dict[date, tuple[Decimal, int | None, str]] = {}
    for d, amt, cat, name in rows:
        if d not in by_date or amt > by_date[d][0]:
            by_date[d] = (amt, cat, name)
    if len(by_date) < 2:
        return None
    all_amounts = [float(v[0]) for v in by_date.values()]
    med = median(all_amounts)
    if med <= 0:
        return None
    core = {d: v for d, v in by_date.items() if abs(float(v[0]) - med) / med <= AMOUNT_BAND}
    if len(core) < 2:
        return None
    dates = sorted(core)
    amounts = [float(core[d][0]) for d in dates]
    core_med = median(amounts)
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    freq = frequency_for_gap(median(gaps))
    if freq is None:
        return None
    n = len(dates)
    if n < 3 and freq != "yearly":
        return None
    lo, hi = WINDOWS[freq]
    regularity = sum(1 for g in gaps if lo <= g <= hi) / len(gaps)
    mad = sum(abs(a - core_med) for a in amounts) / len(amounts) / core_med
    consistency = max(0.0, 1 - mad / 0.15)
    occurrence_score = min(1.0, n / TARGET_N[freq])
    last = dates[-1]
    periods_since = (today - last).days / period_days(freq)
    if periods_since > 1.75:
        return None  # lapsed
    recency = 1.0 if periods_since <= 1.25 else 1.0 - 0.5 * (periods_since - 1.25) / 0.5
    confidence = 0.45 * regularity + 0.25 * consistency + 0.20 * occurrence_score + 0.10 * recency
    if n < 3:
        confidence = min(confidence, 0.69)
    cats = [core[d][1] for d in dates if core[d][1] is not None]
    category_id = max(set(cats), key=lambda c: (cats.count(c), cats[::-1].index(c) * -1)) if cats else None
    anchor = None if freq in ("weekly", "biweekly") else int(median([d.day for d in dates]))
    return {
        "frequency": freq, "n": n, "confidence": round(confidence, 3), "regularity": regularity,
        "amount": Decimal(str(round(core_med, 2))).quantize(CENT), "mad": mad, "last": last,
        "anchor": anchor, "category_id": category_id, "display": core[last][2],
        "regular_gaps": sum(1 for g in gaps if lo <= g <= hi), "gaps": len(gaps),
    }


def _bill_keys(db: Session, user_id: int) -> set[str]:
    return {merchant_key(n) for (n,) in db.execute(select(Bill.name).where(Bill.user_id == user_id, Bill.active.is_(True)))}


def _tracked_keys(db: Session, user_id: int, tx_type: str) -> set[str]:
    return {k for (k,) in db.execute(select(RecurringTransaction.merchant_key).where(
        RecurringTransaction.user_id == user_id, RecurringTransaction.type == tx_type))}


def detect(db: Session, user, today: date, tx_type: str = "expense", include_uncertain: bool = False) -> list[Candidate]:
    since = today - timedelta(days=LOOKBACK_DAYS)
    q = select(Transaction.date, Transaction.amount, Transaction.category_id, Transaction.merchant).where(
        Transaction.user_id == user.id, Transaction.type == tx_type, Transaction.currency == user.currency,
        Transaction.merchant.is_not(None), Transaction.date >= since, Transaction.date <= today)
    groups: dict[str, list] = {}
    for d, amt, cat, name in db.execute(q):
        key = merchant_key(name)
        if key:
            groups.setdefault(key, []).append((d, Decimal(amt), cat, name))

    skip = _tracked_keys(db, user.id, tx_type) | (_bill_keys(db, user.id) if tx_type == "expense" else set())
    cat_names = {cid: n for cid, n in db.execute(select(Category.id, Category.name).where(Category.user_id == user.id))}
    floor = CONFIDENCE_FLOOR if include_uncertain else CONFIDENCE_THRESHOLD

    out: list[Candidate] = []
    for key, rows in groups.items():
        if key in skip:
            continue
        s = _score_group(rows, today)
        if s is None or s["confidence"] < floor:
            continue
        nxt = next_after(s["last"], s["frequency"], today, s["anchor"])
        reasons = [f"{s['n']} payments found, {s['regular_gaps']} of {s['gaps']} gaps match a {s['frequency']} rhythm"]
        reasons.append("the amount is the same each time" if s["mad"] < 0.01
                       else f"the amount varies by about {s['mad'] * 100:.0f}% on average")
        out.append(Candidate(
            type=tx_type, merchant_key=key, merchant=s["display"], amount=s["amount"], frequency=s["frequency"],
            category_id=s["category_id"], category=cat_names.get(s["category_id"]), last_date=s["last"],
            next_expected=nxt, occurrences=s["n"], confidence=s["confidence"], anchor_day=s["anchor"],
            monthly_equivalent=monthly_equivalent(s["amount"], s["frequency"]),
            annual_cost=annual_cost(s["amount"], s["frequency"]), amount_varies=s["mad"] >= 0.01, reasons=reasons))
    out.sort(key=lambda c: (-c.confidence, -float(c.annual_cost), c.merchant_key))
    return out


# ---------- confirmed records ----------

def latest_dates(db: Session, user_id: int, tx_type: str, today: date) -> dict[str, date]:
    """Most recent real transaction date per merchant key (used to keep 'last occurrence' fresh)."""
    rows = db.execute(select(Transaction.merchant, func.max(Transaction.date)).where(
        Transaction.user_id == user_id, Transaction.type == tx_type, Transaction.merchant.is_not(None),
        Transaction.date <= today).group_by(Transaction.merchant))
    out: dict[str, date] = {}
    for name, d in rows:
        k = merchant_key(name)
        if k and (k not in out or d > out[k]):
            out[k] = d
    return out


def view(rec: RecurringTransaction, today: date, latest: dict[str, date], cat_names: dict[int, str]) -> dict:
    stored = rec.last_date
    seen = latest.get(rec.merchant_key)
    last = max([d for d in (stored, seen) if d], default=None)
    nxt = next_after(last, rec.frequency, today, rec.anchor_day) if last else None
    amount = Decimal(rec.amount)
    return {
        "id": rec.id, "type": rec.type, "merchant": rec.merchant, "merchant_key": rec.merchant_key,
        "amount": amount, "frequency": rec.frequency, "category_id": rec.category_id,
        "category": cat_names.get(rec.category_id), "status": rec.status, "reminder": rec.reminder,
        "last_date": last, "next_expected": nxt,
        "days_until_next": (nxt - today).days if nxt else None,
        "monthly_equivalent": monthly_equivalent(amount, rec.frequency),
        "annual_cost": annual_cost(amount, rec.frequency),
        "confidence": rec.confidence, "occurrences": rec.occurrences, "source": rec.source,
        "anchor_day": rec.anchor_day,
    }


def list_records(db: Session, user, today: date, tx_type: str | None = "expense", statuses=("confirmed", "paused")) -> list[dict]:
    q = select(RecurringTransaction).where(RecurringTransaction.user_id == user.id,
                                           RecurringTransaction.status.in_(statuses))
    if tx_type:
        q = q.where(RecurringTransaction.type == tx_type)
    recs = list(db.scalars(q.order_by(RecurringTransaction.id)))
    if not recs:
        return []
    cat_names = {cid: n for cid, n in db.execute(select(Category.id, Category.name).where(Category.user_id == user.id))}
    latest = {}
    for t in {r.type for r in recs}:
        latest[t] = latest_dates(db, user.id, t, today)
    return [view(r, today, latest[r.type], cat_names) for r in recs]


def totals(records: list[dict]) -> dict:
    active = [r for r in records if r["status"] == "confirmed"]
    monthly = sum((r["monthly_equivalent"] for r in active), Decimal("0"))
    annual = sum((r["annual_cost"] for r in active), Decimal("0"))
    return {"count": len(active), "monthly_cost": monthly.quantize(CENT), "annual_cost": annual.quantize(CENT)}


def prior_step(next_date: date, freq: str, anchor: int | None) -> date:
    """The occurrence just before next_date (used for manually-entered records)."""
    return step(next_date, freq, -1, anchor)


def record_from_candidate(user_id: int, cand: Candidate, status: str, *, frequency: str | None = None,
                          category_id: int | None = None, amount=None, merchant: str | None = None) -> RecurringTransaction:
    """Build the stored record for a confirmed/ignored candidate, applying optional user corrections."""
    return RecurringTransaction(
        user_id=user_id, type=cand.type, merchant=merchant or cand.merchant, merchant_key=cand.merchant_key,
        amount=amount or cand.amount, frequency=frequency or cand.frequency,
        category_id=category_id if category_id is not None else cand.category_id,
        last_date=cand.last_date, anchor_day=cand.anchor_day, status=status, confidence=cand.confidence,
        occurrences=cand.occurrences, source="detected")
