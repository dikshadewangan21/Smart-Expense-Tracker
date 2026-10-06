from datetime import date
from decimal import Decimal

import pytest

from app.models.core import Budget
from tests.conftest import auth, register
from tests.helpers import add_tx, cat, user_by_email


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def world(client, db_session, freeze):
    """User A with a hand-computed data set. Today = Sun 2026-10-04 (IST)."""
    token = register(client, "a@example.com")
    u = user_by_email(db_session)
    food, shop, rent, trav = (cat(db_session, u, n) for n in ("Food", "Shopping", "Rent", "Travel"))
    sal = cat(db_session, u, "Salary", "income")
    rows = [  # amount, date, merchant, category, payment method, type
        (50000, date(2026, 10, 1), "Employer", sal, "bank_transfer", "income"),
        (12000, date(2026, 10, 1), "Rent", rent, "bank_transfer", "expense"),
        (1000, date(2026, 10, 2), "Swiggy", food, "upi", "expense"),
        (3000, date(2026, 10, 3), "Amazon", shop, "credit_card", "expense"),
        (500, date(2026, 10, 4), "swiggy ", food, "upi", "expense"),          # name variant, same merchant
        (50000, date(2026, 9, 1), "Employer", sal, "bank_transfer", "income"),
        (12000, date(2026, 9, 1), "Rent", rent, "bank_transfer", "expense"),
        (800, date(2026, 9, 2), "Zomato", food, "upi", "expense"),
        (500, date(2026, 9, 3), "Amazon", shop, "credit_card", "expense"),
        (4000, date(2026, 9, 15), "Zomato", food, "upi", "expense"),
        (2000, date(2026, 9, 20), "IRCTC", trav, "net_banking", "expense"),
        (700, date(2026, 9, 25), "Swiggy", food, "cash", "expense"),
        (12000, date(2026, 8, 1), "Rent", rent, "bank_transfer", "expense"),
        (3000, date(2026, 8, 10), "Zomato", food, "upi", "expense"),
        (6000, date(2026, 8, 15), "IRCTC", trav, "net_banking", "expense"),
    ]
    for amt, d, m, c, pm, ty in rows:
        add_tx(db_session, u, amt, d, m, ty, c, pm)
    db_session.commit()
    return token, u


def get(client, token, path="/api/analytics", **params):
    r = client.get(path, params=params, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def fresh(client, db_session, freeze, email="a@example.com"):
    token = register(client, email)
    return token, user_by_email(db_session, email)


# ---------- core calculations ----------

def test_this_month_totals_and_rates(client, world):
    token, _ = world
    a = get(client, token)
    t = a["totals"]
    assert D(t["income"]) == 50000 and D(t["expenses"]) == 16500 and D(t["net_savings"]) == 33500
    assert t["savings_rate"] == 67.0 and t["transaction_count"] == 5
    assert D(t["average_daily_spending"]) == D("4125.00")  # 16,500 over the 4 days that have happened
    assert a["period"]["start"] == "2026-10-01" and a["period"]["end"] == "2026-10-04" and a["period"]["days_elapsed"] == 4
    assert D(a["previous_totals"]["expenses"]) == 13300  # Sep 1-4: 12000 + 800 + 500
    assert D(a["changes"]["expenses"]) == 3200 and a["changes"]["expenses_pct"] == 24.1


def test_last_month_uses_full_month_for_average(client, world):
    token, _ = world
    a = get(client, token, period="last_month")
    assert D(a["totals"]["expenses"]) == 20000 and a["totals"]["savings_rate"] == 60.0
    assert D(a["totals"]["average_daily_spending"]) == D("666.67")  # 20,000 / 30
    assert D(a["previous_totals"]["expenses"]) == 21000  # August


def test_multi_month_periods(client, world):
    token, _ = world
    a3 = get(client, token, period="last_3_months")  # Aug 1 - Oct 4
    assert D(a3["totals"]["expenses"]) == 16500 + 20000 + 21000
    assert D(get(client, token, period="this_year")["totals"]["income"]) == 100000


def test_custom_range_and_its_previous_span(client, world):
    token, _ = world
    a = get(client, token, period="custom", date_from="2026-10-02", date_to="2026-10-03")
    assert D(a["totals"]["expenses"]) == 4000 and D(a["totals"]["income"]) == 0
    assert a["totals"]["savings_rate"] is None  # zero income -> no rate, not a division error
    assert a["previous_period"]["start"] == "2026-09-30" and a["previous_period"]["end"] == "2026-10-01"
    assert D(a["previous_totals"]["expenses"]) == 12000 and D(a["previous_totals"]["income"]) == 50000


def test_category_totals_shares_and_order(client, world):
    token, _ = world
    cats = get(client, token)["by_category"]
    assert [(c["category"], D(c["amount"]), c["share"], c["count"]) for c in cats] == [
        ("Rent", 12000, 72.7, 1), ("Shopping", 3000, 18.2, 1), ("Food", 1500, 9.1, 2)]
    assert all(c["category_id"] for c in cats)


def test_merchants_grouped_case_and_space_insensitively(client, world):
    token, _ = world
    m = get(client, token)["by_merchant"]
    assert [(x["merchant_key"], D(x["amount"]), x["count"]) for x in m["top"]] == [
        ("rent", 12000, 1), ("amazon", 3000, 1), ("swiggy", 1500, 2)]
    assert D(m["other_total"]) == 0 and D(m["no_merchant_total"]) == 0


def test_payment_methods(client, world):
    token, _ = world
    pm = {x["payment_method"]: D(x["amount"]) for x in get(client, token)["by_payment_method"]}
    assert pm == {"bank_transfer": 12000, "credit_card": 3000, "upi": 1500}


def test_income_vs_expenses_daily_series(client, world):
    token, _ = world
    s = get(client, token)["income_vs_expenses"]
    assert s["granularity"] == "day" and len(s["points"]) == 4
    assert [(p["bucket"], D(p["income"]), D(p["expenses"])) for p in s["points"]] == [
        ("2026-10-01", 50000, 12000), ("2026-10-02", 0, 1000), ("2026-10-03", 0, 3000), ("2026-10-04", 0, 500)]
    s = get(client, token, period="last_3_months")["income_vs_expenses"]
    assert s["granularity"] == "month" and [p["bucket"] for p in s["points"]] == ["2026-08", "2026-09", "2026-10"]


def test_monthly_trend_is_six_months_ending_now(client, world):
    token, _ = world
    tr = get(client, token)["monthly_trend"]
    assert [m["month"] for m in tr] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    by = {m["month"]: m for m in tr}
    assert D(by["2026-08"]["expenses"]) == 21000 and by["2026-08"]["savings_rate"] is None
    assert D(by["2026-09"]["savings"]) == 30000 and by["2026-09"]["savings_rate"] == 60.0
    assert D(by["2026-10"]["expenses"]) == 16500 and D(by["2026-05"]["expenses"]) == 0


def test_month_over_month_and_week_over_week(client, world):
    token, _ = world
    a = get(client, token)
    mom, wow = a["month_over_month"], a["week_over_week"]
    assert (D(mom["current"]), D(mom["previous"]), D(mom["change"]), mom["change_pct"]) == (16500, 13300, 3200, 24.1)
    assert mom["current_range"] == ["2026-10-01", "2026-10-04"] and mom["previous_range"] == ["2026-09-01", "2026-09-04"]
    # Sunday Oct 4: the week started Monday Sep 28; previous week is Sep 21-27 (only the Sep 25 Swiggy, 700)
    assert wow["current_range"] == ["2026-09-28", "2026-10-04"] and wow["previous_range"] == ["2026-09-21", "2026-09-27"]
    assert (D(wow["current"]), D(wow["previous"]), D(wow["change"]), wow["change_pct"]) == (16500, 700, 15800, 2257.1)


def test_highest_category_day_and_largest_transactions(client, world):
    token, _ = world
    a = get(client, token)
    assert a["highest_category"]["category"] == "Rent" and D(a["highest_category"]["amount"]) == 12000
    assert a["highest_spending_day"] == {"date": "2026-10-01", "amount": 12000.0}
    assert [(t["merchant"], D(t["amount"])) for t in a["largest_transactions"]] == [
        ("Rent", 12000), ("Amazon", 3000), ("Swiggy", 1000), ("swiggy ", 500)]
    assert get(client, token, period="last_month")["highest_spending_day"]["date"] == "2026-09-01"


def test_essential_vs_discretionary(client, world):
    token, _ = world
    e = get(client, token)["essential_vs_discretionary"]
    assert (D(e["essential"]), D(e["discretionary"]), D(e["unclassified"])) == (12000, 4500, 0)
    assert e["essential_share"] == 72.7 and e["coverage"] == 100.0 and e["note"] is None


def test_budget_performance_uses_real_budgets(client, db_session, world):
    token, u = world
    db_session.add_all([Budget(user_id=u.id, month=date(2026, 10, 1), total_limit=Decimal("20000")),
                        Budget(user_id=u.id, month=date(2026, 9, 1), total_limit=Decimal("25000"))])
    db_session.commit()
    bp = get(client, token, period="last_3_months")["budget_performance"]
    assert [(b["month"], D(b["limit"]), D(b["spent"]), b["percent_used"], b["partial"]) for b in bp] == [
        ("2026-09", 25000, 20000, 80.0, False), ("2026-10", 20000, 16500, 82.5, True)]
    assert get(client, token, period="last_month")["budget_performance"][0]["month"] == "2026-09"


def test_numbers_are_json_numbers_and_auth_required(client, world):
    token, _ = world
    a = get(client, token)
    assert isinstance(a["totals"]["expenses"], (int, float)) and isinstance(a["by_category"][0]["amount"], (int, float))
    assert client.get("/api/analytics").status_code == 401
    assert client.get("/api/what-changed").status_code == 401


# ---------- What Changed ----------

def test_what_changed_this_month(client, world):
    token, _ = world
    w = get(client, token, "/api/what-changed")
    assert w["comparable"] is True
    assert w["headline"] == "Your spending increased by ₹3,200 compared with the same days last month."
    assert w["drivers_sentence"] == "Most of the increase came from Shopping."
    assert (D(w["spending"]["change"]), w["spending"]["change_pct"]) == (3200, 24.1)
    inc = {r["category"]: r for r in w["increases"]}
    assert list(inc) == ["Shopping", "Food"]  # largest first; Rent unchanged so omitted
    assert (D(inc["Shopping"]["change"]), D(inc["Shopping"]["previous"]), inc["Shopping"]["change_pct"], inc["Shopping"]["share_of_increase"]) == (2500, 500, 500.0, 78.1)
    assert (D(inc["Food"]["change"]), inc["Food"]["share_of_increase"]) == (700, 21.9)
    assert w["decreases"] == [] and D(w["income"]["change"]) == 0
    assert "1–4 Oct" in w["comparison_note"] and "1–4 Sep" in w["comparison_note"]
    # the category changes must add up to the total change
    assert sum(D(r["change"]) for r in w["increases"] + w["decreases"]) == D(w["spending"]["change"])


def test_what_changed_decrease_new_and_stopped_categories(client, world):
    token, _ = world
    w = get(client, token, "/api/what-changed", period="last_month")  # Sep vs Aug
    assert w["headline"] == "Your spending decreased by ₹1,000 compared with the month before."
    assert w["drivers_sentence"] == "Most of the decrease came from Travel."
    assert [(r["category"], D(r["change"]), r["change_pct"]) for r in w["decreases"]] == [("Travel", -4000, -66.7)]
    inc = {r["category"]: r for r in w["increases"]}
    assert D(inc["Food"]["change"]) == 2500 and inc["Shopping"]["is_new"] is True and inc["Shopping"]["change_pct"] is None
    assert sum(D(r["change"]) for r in w["increases"] + w["decreases"]) == D(w["spending"]["change"]) == -1000


def test_what_changed_multiple_drivers_sentence(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    food, shop, trav = (cat(db_session, u, n) for n in ("Food", "Shopping", "Travel"))
    add_tx(db_session, u, 1000, date(2026, 9, 2), "A", category=food)
    for c, amt in ((food, 1000), (shop, 900), (trav, 800)):  # increases: Food +1000... Shopping +900, Travel +800
        add_tx(db_session, u, amt, date(2026, 10, 2), "X", category=c)
    db_session.commit()
    w = get(client, token, "/api/what-changed")
    # increases: Shopping 900, Travel 800, Food 0 (1000 vs 1000: omitted) -> 60% of 1700 is 1020 -> needs both
    assert w["drivers_sentence"] == "Most of the increase came from Shopping and Travel."


def test_what_changed_without_previous_data_or_unchanged(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 500, date(2026, 10, 2), "X", category=cat(db_session, u, "Food"))
    db_session.commit()
    w = get(client, token, "/api/what-changed")
    assert w["comparable"] is False and "no spending recorded" in w["headline"] and w["spending"]["change_pct"] is None
    add_tx(db_session, u, 500, date(2026, 9, 2), "X", category=cat(db_session, u, "Food"))
    db_session.commit()
    w = get(client, token, "/api/what-changed")
    assert w["headline"] == "Your spending is unchanged compared with the same days last month."
    assert w["increases"] == [] and w["decreases"] == [] and w["drivers_sentence"] is None


# ---------- edge cases ----------

def test_no_transactions_at_all(client, db_session, freeze):
    token, _ = fresh(client, db_session, freeze)
    a = get(client, token)
    assert D(a["totals"]["income"]) == 0 and D(a["totals"]["expenses"]) == 0 and a["totals"]["savings_rate"] is None
    assert D(a["totals"]["average_daily_spending"]) == 0
    assert a["by_category"] == [] and a["by_merchant"]["top"] == [] and a["by_payment_method"] == []
    assert a["highest_category"] is None and a["highest_spending_day"] is None and a["largest_transactions"] == []
    assert len(a["monthly_trend"]) == 6 and all(D(m["expenses"]) == 0 for m in a["monthly_trend"])
    assert a["essential_vs_discretionary"]["coverage"] is None and a["budget_performance"] == []
    w = get(client, token, "/api/what-changed")
    assert w["comparable"] is False and w["increases"] == [] and w["decreases"] == []


def test_only_income(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 40000, date(2026, 10, 1), "Employer", "income", cat(db_session, u, "Salary", "income"))
    db_session.commit()
    t = get(client, token)["totals"]
    assert D(t["income"]) == 40000 and D(t["expenses"]) == 0 and t["savings_rate"] == 100.0
    assert D(t["net_savings"]) == 40000 and D(t["average_daily_spending"]) == 0


def test_only_expenses_zero_income(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 800, date(2026, 10, 2), "Cafe", category=cat(db_session, u, "Food"))
    db_session.commit()
    t = get(client, token)["totals"]
    assert D(t["income"]) == 0 and D(t["net_savings"]) == -800 and t["savings_rate"] is None


def test_overspending_gives_negative_savings_rate(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 1000, date(2026, 10, 1), "Employer", "income", cat(db_session, u, "Salary", "income"))
    add_tx(db_session, u, 1500, date(2026, 10, 2), "Shop", category=cat(db_session, u, "Shopping"))
    db_session.commit()
    assert get(client, token)["totals"]["savings_rate"] == -50.0


def test_same_day_transactions_are_summed_for_highest_day(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    food = cat(db_session, u, "Food")
    for _ in range(3):
        add_tx(db_session, u, 400, date(2026, 10, 2), "Cafe", category=food)  # 1,200 across one day
    add_tx(db_session, u, 1000, date(2026, 10, 3), "Big", category=food)       # single largest transaction
    db_session.commit()
    a = get(client, token)
    assert a["highest_spending_day"] == {"date": "2026-10-02", "amount": 1200.0}
    assert D(a["largest_transactions"][0]["amount"]) == 1000


def test_duplicate_transactions_are_both_counted(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    for _ in range(2):
        add_tx(db_session, u, 649, date(2026, 10, 2), "Netflix", category=cat(db_session, u, "Subscriptions"))
    db_session.commit()
    a = get(client, token)
    assert D(a["totals"]["expenses"]) == 1298 and a["by_merchant"]["top"][0]["count"] == 2


def test_transfers_are_excluded_everywhere(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 99999, date(2026, 10, 2), "Own account", "transfer")
    add_tx(db_session, u, 100, date(2026, 10, 2), "Cafe", category=cat(db_session, u, "Food"))
    db_session.commit()
    a = get(client, token)
    assert D(a["totals"]["expenses"]) == 100 and D(a["totals"]["income"]) == 0 and a["totals"]["transaction_count"] == 1
    assert D(get(client, token, "/api/what-changed")["spending"]["current"]) == 100


def test_other_currency_is_excluded_and_reported(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 100, date(2026, 10, 2), "Cafe", category=cat(db_session, u, "Food"))
    add_tx(db_session, u, 500, date(2026, 10, 2), "Overseas", currency="USD")
    db_session.commit()
    a = get(client, token)
    assert D(a["totals"]["expenses"]) == 100 and a["excluded_other_currency"] == 1


def test_future_dated_transactions_do_not_count_yet(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    food = cat(db_session, u, "Food")
    add_tx(db_session, u, 100, date(2026, 10, 2), "Cafe", category=food)
    add_tx(db_session, u, 777, date(2026, 10, 10), "Booked trip", category=food)
    db_session.commit()
    assert D(get(client, token)["totals"]["expenses"]) == 100


def test_uncategorized_spending_and_classification_note(client, db_session, freeze):
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 5000, date(2026, 10, 2), "Mystery")
    add_tx(db_session, u, 1000, date(2026, 10, 3), "Cafe", category=cat(db_session, u, "Food"))
    db_session.commit()
    a = get(client, token)
    assert a["by_category"][0]["category"] == "Uncategorized" and a["by_category"][0]["category_id"] is None
    assert a["highest_category"]["category"] == "Food"  # real categories only
    e = a["essential_vs_discretionary"]
    assert D(e["unclassified"]) == 5000 and e["coverage"] == 16.7 and e["note"]


def test_timezone_boundary_decides_which_month_is_current(client, db_session, freeze):
    # 2026-09-30 19:00 UTC is already 1 Oct 00:30 in India but still 30 Sep in UTC.
    freeze("2026-09-30T19:00:00+00:00")
    token, u = fresh(client, db_session, freeze)
    add_tx(db_session, u, 100, date(2026, 9, 30), "Old", category=cat(db_session, u, "Food"))
    add_tx(db_session, u, 200, date(2026, 10, 1), "New", category=cat(db_session, u, "Food"))
    db_session.commit()
    ist = get(client, token)
    assert (ist["period"]["start"], ist["period"]["end"]) == ("2026-10-01", "2026-10-01") and D(ist["totals"]["expenses"]) == 200
    u.timezone = "UTC"
    db_session.commit()
    utc = get(client, token)
    assert (utc["period"]["start"], utc["period"]["end"]) == ("2026-09-01", "2026-09-30") and D(utc["totals"]["expenses"]) == 100
    u.timezone = "Not/AZone"  # an invalid stored zone falls back to Asia/Kolkata instead of crashing
    db_session.commit()
    assert get(client, token)["period"]["start"] == "2026-10-01"


def test_invalid_period_requests_are_422(client, world):
    token, _ = world
    h = auth(token)
    assert client.get("/api/analytics", params={"period": "forever"}, headers=h).status_code == 422
    assert client.get("/api/analytics", params={"period": "custom"}, headers=h).status_code == 422
    r = client.get("/api/analytics", params={"period": "custom", "date_from": "2026-10-05", "date_to": "2026-10-01"}, headers=h)
    assert r.status_code == 422 and "start date" in r.json()["detail"]
    assert client.get("/api/what-changed", params={"period": "custom", "date_from": "2026-10-05"}, headers=h).status_code == 422


def test_analytics_isolated_between_users(client, db_session, world):
    token_a, _ = world
    client.cookies.clear()
    token_b = register(client, "b@example.com")
    b = get(client, token_b)
    assert D(b["totals"]["income"]) == 0 and D(b["totals"]["expenses"]) == 0 and b["by_category"] == []
    assert b["largest_transactions"] == [] and b["by_merchant"]["top"] == []
    assert get(client, token_b, "/api/what-changed")["increases"] == []
    assert D(get(client, token_a)["totals"]["expenses"]) == 16500


# ---------- drill-down filters used by chart clicks ----------

def test_drilldown_filters_on_transactions(client, db_session, world):
    token, u = world
    add_tx(db_session, u, 250, date(2026, 10, 2), "Swiggy Instamart", category=cat(db_session, u, "Groceries"))
    add_tx(db_session, u, 90, date(2026, 10, 2), "Mystery")
    db_session.commit()

    def ids(**p):
        r = client.get("/api/transactions", params=p, headers=auth(token))
        assert r.status_code == 200, r.text
        return sorted((x["merchant"] or "") for x in r.json()["items"])

    assert ids(merchant_exact="  SWIGGY ", type="expense", date_from="2026-10-01", date_to="2026-10-04") == ["Swiggy", "swiggy "]
    assert "Swiggy Instamart" in ids(merchant="swiggy") and "Swiggy Instamart" not in ids(merchant_exact="swiggy")
    assert ids(uncategorized="true") == ["Mystery"]


def test_average_daily_ignores_days_that_have_not_happened_yet(client, world):
    token, _ = world
    a = get(client, token, period="custom", date_from="2026-10-01", date_to="2026-10-31")  # runs into the future
    assert a["period"]["days"] == 31 and a["period"]["days_elapsed"] == 4
    assert D(a["totals"]["average_daily_spending"]) == D("4125.00")  # 16,500 / 4 elapsed days, not / 31
    fully_future = get(client, token, period="custom", date_from="2026-11-01", date_to="2026-11-30")
    assert fully_future["period"]["days_elapsed"] == 0 and fully_future["totals"]["average_daily_spending"] is None
