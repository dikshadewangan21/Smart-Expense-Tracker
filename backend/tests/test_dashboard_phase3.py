from datetime import date
from decimal import Decimal

from tests.conftest import auth, register
from tests.helpers import add_tx, cat, monthly, user_by_email


def D(x):
    return Decimal(str(x))


def test_empty_dashboard_has_every_new_section(client, db_session, freeze):
    t = register(client)
    d = client.get("/api/dashboard", headers=auth(t)).json()
    assert d["as_of"] == "2026-10-04"
    assert d["upcoming_payments"]["items"] == [] and set(d["upcoming_payments"]["groups"]) == {"overdue", "today", "tomorrow", "this_week", "later"}
    r = d["recurring_summary"]
    assert (r["subscriptions_count"], D(r["total_monthly"]), D(r["total_annual"]), r["pending_review"]) == (0, 0, 0, 0)
    a = d["analytics_summary"]
    assert a["savings_rate"] is None and D(a["average_daily_spending"]) == 0 and a["highest_category"] is None
    assert d["what_changed"]["comparable"] is False


def test_dashboard_sections_match_the_dedicated_endpoints(client, db_session, freeze):
    t = register(client)
    u = user_by_email(db_session)
    food, shop = cat(db_session, u, "Food"), cat(db_session, u, "Shopping")
    add_tx(db_session, u, 50000, date(2026, 10, 1), "Employer", "income", cat(db_session, u, "Salary", "income"))
    add_tx(db_session, u, 1500, date(2026, 10, 2), "Swiggy", category=food)
    add_tx(db_session, u, 3000, date(2026, 10, 3), "Amazon", category=shop)
    add_tx(db_session, u, 800, date(2026, 9, 2), "Swiggy", category=food)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(t))
    monthly(db_session, u, "Gym", 1500, date(2026, 9, 5), 6)  # detected but not confirmed
    client.post("/api/bills", json={"name": "Rent", "kind": "rent", "amount": "12000", "due_date": "2026-10-06", "frequency": "monthly"}, headers=auth(t))

    d = client.get("/api/dashboard", headers=auth(t)).json()
    assert d["upcoming_payments"] == client.get("/api/upcoming", params={"days": 30}, headers=auth(t)).json()
    assert d["what_changed"] == client.get("/api/what-changed", headers=auth(t)).json()
    an = client.get("/api/analytics", headers=auth(t)).json()
    assert d["analytics_summary"]["savings_rate"] == an["totals"]["savings_rate"]
    assert d["analytics_summary"]["average_daily_spending"] == an["totals"]["average_daily_spending"]
    assert d["analytics_summary"]["highest_category"]["category"] == an["highest_category"]["category"]
    assert d["analytics_summary"]["month_over_month"] == an["month_over_month"]

    r = d["recurring_summary"]
    assert r["subscriptions_count"] == 1 and D(r["subscriptions_monthly"]) == 649 and D(r["subscriptions_annual"]) == 7788
    assert D(r["bills_monthly"]) == 12000 and D(r["total_monthly"]) == 12649 and D(r["total_annual"]) == 151788
    assert r["pending_review"] == 1  # Gym awaits review
    # What Changed on the dashboard is the same like-for-like comparison
    assert "compared with the same days last month" in d["what_changed"]["headline"]


def test_health_score_recurring_load_now_includes_bills(client, db_session, freeze):
    t = register(client)
    u = user_by_email(db_session)
    add_tx(db_session, u, 50000, date(2026, 10, 1), "Employer", "income", cat(db_session, u, "Salary", "income"))
    add_tx(db_session, u, 1000, date(2026, 10, 2), "Cafe", category=cat(db_session, u, "Food"))
    db_session.commit()
    client.post("/api/bills", json={"name": "Rent", "kind": "rent", "amount": "15000", "due_date": "2026-10-06", "frequency": "monthly"}, headers=auth(t))
    comp = {c["key"]: c for c in client.get("/api/dashboard", headers=auth(t)).json()["financial_health"]["components"]}
    assert comp["recurring_load"]["value"] == 30.0  # 15,000 of 50,000 income
    assert comp["recurring_load"]["points"] == 6.0  # (1 - 0.30/0.5) * 15


def test_dashboard_isolated(client, db_session, freeze):
    ta = register(client, "a@example.com")
    ua = user_by_email(db_session)
    monthly(db_session, ua, "Netflix", 649, date(2026, 9, 8), 6)
    client.post("/api/bills", json={"name": "Rent", "amount": "12000", "due_date": "2026-10-06"}, headers=auth(ta))
    client.cookies.clear()
    tb = register(client, "b@example.com")
    d = client.get("/api/dashboard", headers=auth(tb)).json()
    assert d["upcoming_payments"]["items"] == [] and d["recurring_summary"]["pending_review"] == 0
    assert D(d["recurring_summary"]["total_monthly"]) == 0
