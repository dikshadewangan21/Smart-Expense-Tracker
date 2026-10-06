from datetime import date

import pytest

from app.services.periods import resolve_period


def p(kind, today=date(2026, 10, 4), **kw):
    return resolve_period(kind, today, **kw)


def test_this_month_is_month_to_date_vs_same_days_last_month():
    x = p("this_month")
    assert (x.start, x.end, x.prev_start, x.prev_end) == (date(2026, 10, 1), date(2026, 10, 4), date(2026, 9, 1), date(2026, 9, 4))
    assert x.days == x.prev_days == 4


def test_last_month_full_vs_month_before():
    x = p("last_month")
    assert (x.start, x.end, x.prev_start, x.prev_end) == (date(2026, 9, 1), date(2026, 9, 30), date(2026, 8, 1), date(2026, 8, 31))


def test_last_3_and_6_months_are_calendar_aligned():
    a, b = p("last_3_months"), p("last_6_months")
    assert (a.start, a.end, a.prev_start, a.prev_end) == (date(2026, 8, 1), date(2026, 10, 4), date(2026, 5, 1), date(2026, 7, 4))
    assert (b.start, b.prev_start, b.prev_end) == (date(2026, 5, 1), date(2025, 11, 1), date(2026, 4, 4))


def test_this_year():
    x = p("this_year")
    assert (x.start, x.end, x.prev_start, x.prev_end) == (date(2026, 1, 1), date(2026, 10, 4), date(2025, 1, 1), date(2025, 10, 4))


def test_custom_range_previous_is_equally_long_and_adjacent():
    x = p("custom", date_from=date(2026, 10, 1), date_to=date(2026, 10, 3))
    assert (x.prev_start, x.prev_end) == (date(2026, 9, 28), date(2026, 9, 30)) and x.days == x.prev_days == 3
    one = p("custom", date_from=date(2026, 10, 2), date_to=date(2026, 10, 2))
    assert one.days == 1 and one.prev_start == one.prev_end == date(2026, 10, 1)


def test_month_end_clamping():
    x = p("this_month", today=date(2026, 3, 31))
    assert x.prev_end == date(2026, 2, 28)  # no Feb 31
    assert p("this_month", today=date(2028, 3, 31)).prev_end == date(2028, 2, 29)
    assert p("this_month", today=date(2026, 1, 15)).prev_start == date(2025, 12, 1)  # year rollover


@pytest.mark.parametrize("kw", [
    dict(date_from=None, date_to=date(2026, 10, 1)),
    dict(date_from=date(2026, 10, 1), date_to=None),
    dict(date_from=date(2026, 10, 5), date_to=date(2026, 10, 1)),
    dict(date_from=date(2000, 1, 1), date_to=date(2026, 10, 1)),
])
def test_invalid_custom_ranges_rejected(kw):
    with pytest.raises(ValueError):
        resolve_period("custom", date(2026, 10, 4), **kw)


def test_unknown_period_rejected():
    with pytest.raises(ValueError):
        resolve_period("last_week", date(2026, 10, 4))
