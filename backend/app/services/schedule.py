"""Date arithmetic for repeating payments. Pure functions, no database access.

Month-based frequencies keep an *anchor day* so a payment due on the 31st lands on
Feb 28/29, then Mar 31 again (not Mar 28).
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.services.periods import add_months_anchored

FREQUENCIES = ("weekly", "biweekly", "monthly", "quarterly", "yearly")
PER_YEAR = {"weekly": Decimal(52), "biweekly": Decimal(26), "monthly": Decimal(12),
            "quarterly": Decimal(4), "yearly": Decimal(1)}
_DAYS = {"weekly": 7, "biweekly": 14}
_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}
CENT = Decimal("0.01")


def monthly_equivalent(amount, freq: str) -> Decimal:
    return (Decimal(amount) * PER_YEAR[freq] / 12).quantize(CENT, ROUND_HALF_UP)


def annual_cost(amount, freq: str) -> Decimal:
    return (Decimal(amount) * PER_YEAR[freq]).quantize(CENT, ROUND_HALF_UP)


_NOMINAL_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30, "quarterly": 91, "yearly": 365}


def period_days(freq: str) -> int:
    """Nominal length of one period, for recency checks only (not for date arithmetic)."""
    return _NOMINAL_DAYS[freq]


def step(base: date, freq: str, k: int, anchor_day: int | None = None) -> date:
    """The schedule date k periods after (or before, k<0) base."""
    if freq in _DAYS:
        return base + timedelta(days=_DAYS[freq] * k)
    return add_months_anchored(base, _MONTHS[freq] * k, anchor_day or base.day)


def occurrences_between(base: date, freq: str, start: date, end: date, anchor_day: int | None = None) -> list[date]:
    """All schedule dates (base + k periods for any integer k) inside [start, end]."""
    if end < start:
        return []
    if freq in _DAYS:
        d = _DAYS[freq]
        k = -((base - start).days // d)  # ceil((start-base)/d)
    else:
        mp = _MONTHS[freq]
        k = ((start.year * 12 + start.month) - (base.year * 12 + base.month)) // mp - 1
    out: list[date] = []
    for _ in range(100000):
        dt = step(base, freq, k, anchor_day)
        if dt > end:
            break
        if dt >= start:
            out.append(dt)
        k += 1
    return out


def next_after(base: date, freq: str, ref: date, anchor_day: int | None = None) -> date:
    """First schedule date on/after ref that belongs to the *next* payment cycle after base.

    A date counts as the next cycle only if it is more than half a period after base. That way a
    payment made a few days early (Netflix due on the 8th, paid on the 3rd) is treated as that
    month's payment, and the next one is next month's, not "the 8th again".
    """
    min_gap = period_days(freq) // 2
    lo = max(ref, base + timedelta(days=min_gap + 1))
    for window in (400, 800):
        found = occurrences_between(base, freq, lo, lo + timedelta(days=window), anchor_day)
        if found:
            return found[0]
    raise ValueError("could not compute the next occurrence")
