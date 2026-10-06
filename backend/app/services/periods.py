"""Period resolution. All dates are plain dates already expressed in the user's timezone.

Every period carries a like-for-like *previous* period used for comparisons:
  this_month      month-to-date              vs the same days of last month
  last_month      the full previous month    vs the full month before it
  last_3_months   3 calendar months ending with the current (month-to-date)
                                             vs the same span 3 months earlier
  last_6_months   same idea, 6 months
  this_year       Jan 1 .. today             vs Jan 1 .. the same day last year
  custom          date_from..date_to         vs the equally long span just before it
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

PERIOD_KINDS = ("this_month", "last_month", "last_3_months", "last_6_months", "this_year", "custom")
MAX_CUSTOM_DAYS = 3660


def add_months(d: date, n: int) -> date:
    """Shift by n months, clamping the day (Jan 31 + 1 month = Feb 28/29)."""
    y, m0 = divmod(d.year * 12 + (d.month - 1) + n, 12)
    m = m0 + 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def add_months_anchored(d: date, n: int, anchor_day: int | None) -> date:
    """Like add_months but lands on anchor_day (clamped) so Jan 31 -> Feb 28 -> Mar 31, not Mar 28."""
    y, m0 = divmod(d.year * 12 + (d.month - 1) + n, 12)
    m = m0 + 1
    return date(y, m, min(anchor_day or d.day, monthrange(y, m)[1]))


def month_end(d: date) -> date:
    return d.replace(day=monthrange(d.year, d.month)[1])


@dataclass(frozen=True)
class Period:
    kind: str
    start: date
    end: date
    prev_start: date
    prev_end: date
    label: str
    prev_label: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def prev_days(self) -> int:
        return (self.prev_end - self.prev_start).days + 1


def resolve_period(kind: str, today: date, date_from: date | None = None, date_to: date | None = None) -> Period:
    first = today.replace(day=1)
    if kind == "this_month":
        return Period(kind, first, today, add_months(first, -1), add_months(today, -1),
                      "this month so far", "the same days last month")
    if kind == "last_month":
        s = add_months(first, -1)
        e = month_end(s)
        ps = add_months(s, -1)
        return Period(kind, s, e, ps, month_end(ps), "last month", "the month before")
    if kind in ("last_3_months", "last_6_months"):
        n = 3 if kind == "last_3_months" else 6
        s = add_months(first, -(n - 1))
        return Period(kind, s, today, add_months(s, -n), add_months(today, -n),
                      f"the last {n} months", f"the {n} months before")
    if kind == "this_year":
        s = date(today.year, 1, 1)
        return Period(kind, s, today, date(today.year - 1, 1, 1), add_months(today, -12),
                      "this year so far", "the same days last year")
    if kind == "custom":
        if date_from is None or date_to is None:
            raise ValueError("Choose both a start and an end date for a custom range.")
        if date_from > date_to:
            raise ValueError("The start date must be on or before the end date.")
        n = (date_to - date_from).days + 1
        if n > MAX_CUSTOM_DAYS:
            raise ValueError("Custom ranges can span at most 10 years.")
        pe = date_from - timedelta(days=1)
        return Period(kind, date_from, date_to, pe - timedelta(days=n - 1), pe,
                      "the selected range", "the range just before it")
    raise ValueError(f"Unknown period '{kind}'.")
