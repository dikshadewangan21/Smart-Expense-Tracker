from datetime import date
from decimal import Decimal

import pytest

from app.models.core import Transaction
from tests.conftest import auth, register
from tests.helpers import add_tx, cat, monthly, user_by_email


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def me(client, db_session, freeze):
    """Registered user A, clock frozen at Sun 2026-10-04 (IST)."""
    return register(client, "a@example.com"), user_by_email(db_session)


def mk(client, t, **over):
    body = {"name": "Electricity", "kind": "electricity", "amount": "1850", "due_date": "2026-10-08", "frequency": "monthly"}
    body.update(over)
    r = client.post("/api/bills", json=body, headers=auth(t))
    assert r.status_code == 201, r.text
    return r.json()


def pay(client, t, bill_id, **body):
    return client.post(f"/api/bills/{bill_id}/pay", json=body, headers=auth(t))


# ---------- create / validate ----------

def test_create_returns_computed_fields(client, me):
    t, u = me
    b = mk(client, t, name="  Home   Internet ", kind="internet", notes=" router rental included ", reminder_days=[1, 7, 3, 3])
    assert b["name"] == "Home Internet" and b["notes"] == "router rental included"
    assert b["reminder_days"] == [7, 3, 1] and b["status"] == "upcoming" and b["days_until"] == 4
    assert D(b["monthly_equivalent"]) == D("1850.00") and b["paid"] is False and b["active"] is True


def test_every_kind_and_frequency_is_accepted(client, me):
    t, _ = me
    for kind in ("rent", "electricity", "internet", "phone", "insurance", "emi", "credit_card", "custom"):
        mk(client, t, name=f"k-{kind}", kind=kind)
    for freq in ("once", "weekly", "monthly", "quarterly", "yearly"):
        b = mk(client, t, name=f"f-{freq}", frequency=freq)
        assert (b["monthly_equivalent"] is None) == (freq == "once")


def test_default_reminders_and_explicit_empty(client, me):
    t, _ = me
    assert mk(client, t, name="A")["reminder_days"] == [7, 3, 1, 0]
    assert mk(client, t, name="B", reminder_days=[])["reminder_days"] == []


@pytest.mark.parametrize("bad", [
    {"amount": "0"}, {"amount": "-5"}, {"amount": "10.999"}, {"name": "   "}, {"name": ""}, {"frequency": "daily"},
    {"kind": "bogus"}, {"reminder_days": [61]}, {"reminder_days": [-1]}, {"reminder_days": [1, 2, 3, 4, 5, 6, 7]},
    {"due_date": "1999-12-31"}, {"due_date": "not-a-date"}, {"notes": "x" * 1001},
])
def test_invalid_bills_rejected(client, me, bad):
    t, _ = me
    body = {"name": "X", "amount": "100", "due_date": "2026-10-08", "frequency": "monthly", **bad}
    assert client.post("/api/bills", json=body, headers=auth(t)).status_code == 422


def test_category_must_be_own_expense_category(client, db_session, me):
    t, u = me
    bills_cat = cat(db_session, u, "Bills")
    assert mk(client, t, category_id=bills_cat.id, name="Cat ok")["category"] == "Bills"
    salary = cat(db_session, u, "Salary", "income")
    body = {"name": "X", "amount": "1", "due_date": "2026-10-08"}
    assert client.post("/api/bills", json={**body, "category_id": salary.id}, headers=auth(t)).status_code == 422
    assert client.post("/api/bills", json={**body, "category_id": 99999}, headers=auth(t)).status_code == 422


# ---------- status ----------

def test_status_overdue_today_upcoming_and_days(client, me):
    t, _ = me
    out = {}
    for name, due in (("past", "2026-10-03"), ("today", "2026-10-04"), ("next", "2026-10-05"), ("far", "2026-12-01")):
        b = mk(client, t, name=name, due_date=due, frequency="once")
        out[name] = (b["status"], b["days_until"])
    assert out == {"past": ("overdue", -1), "today": ("due_today", 0), "next": ("upcoming", 1), "far": ("upcoming", 58)}


# ---------- read / update / delete ----------

def test_get_update_and_reopen_paid_bill(client, me):
    t, _ = me
    b = mk(client, t, name="Insurance", kind="insurance", amount="18000", due_date="2026-10-20", frequency="once")
    assert client.get(f"/api/bills/{b['id']}", headers=auth(t)).json()["name"] == "Insurance"
    pay(client, t, b["id"])
    assert client.get(f"/api/bills/{b['id']}", headers=auth(t)).json()["status"] == "paid"
    body = {"name": "Insurance premium", "kind": "insurance", "amount": "19000", "due_date": "2026-10-20", "frequency": "once", "notes": "renewed"}
    r = client.put(f"/api/bills/{b['id']}", json=body, headers=auth(t)).json()
    assert r["name"] == "Insurance premium" and D(r["amount"]) == 19000 and r["status"] == "paid"  # same date: stays paid
    r = client.put(f"/api/bills/{b['id']}", json={**body, "due_date": "2027-10-20", "frequency": "yearly"}, headers=auth(t)).json()
    assert r["status"] == "upcoming" and r["paid"] is False and r["frequency"] == "yearly"
    r = client.put(f"/api/bills/{b['id']}", json={**body, "due_date": "2027-10-20", "frequency": "yearly", "active": False}, headers=auth(t)).json()
    assert r["status"] == "inactive"
    assert client.put(f"/api/bills/{b['id']}", json={**body, "amount": "0"}, headers=auth(t)).status_code == 422


def test_delete_keeps_recorded_expenses(client, db_session, me):
    t, u = me
    b = mk(client, t)
    assert pay(client, t, b["id"]).status_code == 200
    assert client.delete(f"/api/bills/{b['id']}", headers=auth(t)).status_code == 204
    assert client.get(f"/api/bills/{b['id']}", headers=auth(t)).status_code == 404
    assert client.delete(f"/api/bills/{b['id']}", headers=auth(t)).status_code == 404
    assert db_session.query(Transaction).filter(Transaction.user_id == u.id, Transaction.source == "bill").count() == 1


# ---------- paying ----------

def test_pay_one_time_bill_creates_expense_and_closes_it(client, db_session, me):
    t, u = me
    bills_cat = cat(db_session, u, "Bills")
    b = mk(client, t, name="Passport fee", frequency="once", amount="1500", category_id=bills_cat.id)
    r = pay(client, t, b["id"], payment_method="upi")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["bill"]["status"] == "paid" and out["bill"]["last_paid"] == "2026-10-04" and out["transaction_id"]
    tx = client.get(f"/api/transactions/{out['transaction_id']}", headers=auth(t)).json()
    assert (tx["merchant"], D(tx["amount"]), tx["category"], tx["payment_method"], tx["date"], tx["source"], tx["type"]) == (
        "Passport fee", 1500, "Bills", "upi", "2026-10-04", "bill", "expense")
    assert pay(client, t, b["id"]).status_code == 409  # cannot pay twice


@pytest.mark.parametrize("freq,due,next_due", [
    ("weekly", "2026-10-06", "2026-10-13"),
    ("monthly", "2026-10-12", "2026-11-12"),
    ("quarterly", "2026-10-15", "2027-01-15"),
    ("yearly", "2026-12-20", "2027-12-20"),
])
def test_paying_a_repeating_bill_advances_one_period(client, me, freq, due, next_due):
    t, _ = me
    b = mk(client, t, frequency=freq, due_date=due)
    out = pay(client, t, b["id"]).json()["bill"]
    assert out["due_date"] == next_due and out["paid"] is False and out["status"] == "upcoming" and out["last_paid"] == "2026-10-04"


def test_month_end_bill_keeps_its_anchor_day(client, me):
    t, _ = me
    b = mk(client, t, name="Rent", due_date="2026-10-31")
    seen = []
    for _ in range(4):
        seen.append(pay(client, t, b["id"]).json()["bill"]["due_date"])
    assert seen == ["2026-11-30", "2026-12-31", "2027-01-31", "2027-02-28"]


def test_overdue_bill_clears_one_cycle_per_payment(client, me):
    t, _ = me
    b = mk(client, t, due_date="2026-08-20")
    assert b["status"] == "overdue"
    out = pay(client, t, b["id"]).json()["bill"]
    assert out["due_date"] == "2026-09-20" and out["status"] == "overdue"  # still a cycle behind
    out = pay(client, t, b["id"]).json()["bill"]
    assert out["due_date"] == "2026-10-20" and out["status"] == "upcoming"


def test_auto_repeat_off_behaves_like_one_time(client, me):
    t, _ = me
    b = mk(client, t, auto_repeat=False)
    assert pay(client, t, b["id"]).json()["bill"]["status"] == "paid"


def test_pay_without_expense_with_custom_amount_and_past_date(client, db_session, me):
    t, u = me
    b = mk(client, t)
    r = pay(client, t, b["id"], create_transaction=False).json()
    assert r["transaction_id"] is None and db_session.query(Transaction).filter(Transaction.user_id == u.id).count() == 0
    b2 = mk(client, t, name="Water")
    r = pay(client, t, b2["id"], amount="1700", paid_on="2026-10-01").json()
    tx = client.get(f"/api/transactions/{r['transaction_id']}", headers=auth(t)).json()
    assert D(tx["amount"]) == 1700 and tx["date"] == "2026-10-01" and D(r["bill"]["amount"]) == 1850  # bill amount unchanged
    assert r["bill"]["last_paid"] == "2026-10-01"


def test_pay_rejections(client, me):
    t, _ = me
    b = mk(client, t)
    assert pay(client, t, b["id"], paid_on="2026-10-05").status_code == 422      # future
    assert pay(client, t, b["id"], amount="0").status_code == 422
    assert pay(client, t, b["id"], account_id=424242).status_code == 422
    assert pay(client, t, b["id"], payment_method="bitcoin").status_code == 422
    assert pay(client, t, 987654).status_code == 404
    off = mk(client, t, name="Off", active=False)
    assert pay(client, t, off["id"]).status_code == 409


# ---------- list / summary ----------

def test_list_default_filters_sort_and_summary(client, me):
    t, _ = me
    mk(client, t, name="Overdue one", due_date="2026-09-28", frequency="once", amount="500")
    mk(client, t, name="Phone", due_date="2026-10-04", amount="299")
    mk(client, t, name="Internet", due_date="2026-10-05", amount="999")
    mk(client, t, name="Rent", due_date="2026-10-11", amount="12000")
    mk(client, t, name="Gym weekly", due_date="2026-10-20", amount="100", frequency="weekly")
    done = mk(client, t, name="Done", frequency="once", amount="50")
    pay(client, t, done["id"])
    mk(client, t, name="Switched off", active=False, amount="77")

    r = client.get("/api/bills", headers=auth(t)).json()
    assert [b["name"] for b in r["items"]] == ["Overdue one", "Phone", "Internet", "Rent", "Gym weekly"]  # by due date; no paid/inactive
    s = r["summary"]
    assert s["overdue_count"] == 1 and D(s["overdue_total"]) == 500
    assert D(s["due_next_7_days_total"]) == 299 + 999 + 12000   # Oct 4, 5, 11 (11 is exactly 7 days out)
    assert D(s["monthly_commitment"]) == D(299 + 999 + 12000) + (Decimal(100) * 52 / 12).quantize(Decimal("0.01"))  # once-bills excluded

    names = lambda **p: [b["name"] for b in client.get("/api/bills", params=p, headers=auth(t)).json()["items"]]
    assert names(status="paid") == ["Done"] and names(status="inactive") == ["Switched off"] and names(status="overdue") == ["Overdue one"]
    assert names(sort="amount") == ["Rent", "Internet", "Overdue one", "Phone", "Gym weekly"]  # 12000, 999, 500, 299, 100
    assert names(sort="name")[0] == "Gym weekly"
    assert client.get("/api/bills", params={"status": "weird"}, headers=auth(t)).status_code == 422
    assert client.get("/api/bills", params={"sort": "weird"}, headers=auth(t)).status_code == 422


def test_empty_bills(client, me):
    t, _ = me
    r = client.get("/api/bills", headers=auth(t)).json()
    assert r["items"] == [] and D(r["summary"]["monthly_commitment"]) == 0 and r["summary"]["overdue_count"] == 0


# ---------- upcoming payments ----------

def confirm(client, t, key, **kw):
    r = client.post("/api/recurring/confirm", json={"merchant_key": key, **kw}, headers=auth(t))
    assert r.status_code == 201, r.text
    return r.json()


def test_upcoming_combines_bills_and_recurring_in_groups(client, db_session, me):
    t, u = me
    mk(client, t, name="Old bill", due_date="2026-09-28", frequency="once", amount="500")
    mk(client, t, name="Phone", due_date="2026-10-04", amount="299")
    mk(client, t, name="Internet", due_date="2026-10-05", amount="999")
    mk(client, t, name="Electricity", due_date="2026-10-08", amount="1850")
    mk(client, t, name="Rent", due_date="2026-10-11", amount="12000")
    mk(client, t, name="Credit card", due_date="2026-10-20", frequency="once", amount="3000")
    mk(client, t, name="Insurance", due_date="2026-12-20", frequency="yearly", amount="18000")
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    confirm(client, t, "netflix")

    r = client.get("/api/upcoming", params={"days": 10}, headers=auth(t)).json()
    g = {k: [(i["name"], i["days_until"]) for i in v] for k, v in r["groups"].items()}
    assert g == {"overdue": [("Old bill", -6)], "today": [("Phone", 0)], "tomorrow": [("Internet", 1)],
                 "this_week": [("Electricity", 4), ("Netflix", 4), ("Rent", 7)], "later": []}
    kinds = {i["name"]: i["kind"] for i in r["items"]}
    assert kinds["Netflix"] == "recurring" and kinds["Rent"] == "bill"
    assert [i["name"] for i in r["items"]] == ["Old bill", "Phone", "Internet", "Electricity", "Netflix", "Rent"]  # chronological
    assert D(r["totals"]["overdue"]) == 500 and D(r["totals"]["next_7_days"]) == 299 + 999 + 1850 + 649 + 12000
    assert r["counts"] == {"overdue": 1, "today": 1, "tomorrow": 1, "this_week": 3, "later": 0}

    wide = client.get("/api/upcoming", headers=auth(t)).json()  # default 60-day horizon
    names = [i["name"] for i in wide["items"]]
    assert "Credit card" in names and "Insurance" not in names  # Dec 20 is 77 days away
    assert next(i for i in wide["items"] if i["name"] == "Credit card")["group"] == "later"
    assert names.count("Rent") == 2  # Oct 11 and the repeat on Nov 11


def test_upcoming_projects_weekly_and_overdue_repeating_bills(client, me):
    t, _ = me
    mk(client, t, name="Maid", frequency="weekly", due_date="2026-10-06", amount="100")
    mk(client, t, name="Lapsed monthly", due_date="2026-09-20", amount="700")
    r = client.get("/api/upcoming", params={"days": 20}, headers=auth(t)).json()
    maid = [i["days_until"] for i in r["items"] if i["name"] == "Maid"]
    assert maid == [2, 9, 16]
    lapsed = [(i["due_date"], i["group"]) for i in r["items"] if i["name"] == "Lapsed monthly"]
    assert lapsed == [("2026-09-20", "overdue"), ("2026-10-20", "later")]  # one overdue entry, then the future cycle


def test_recurring_with_a_bills_name_is_not_listed_twice(client, db_session, me):
    t, u = me
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    confirm(client, t, "netflix")
    assert [i["kind"] for i in client.get("/api/upcoming", params={"days": 10}, headers=auth(t)).json()["items"]] == ["recurring"]
    mk(client, t, name="NETFLIX ", due_date="2026-10-09", amount="649")
    items = client.get("/api/upcoming", params={"days": 10}, headers=auth(t)).json()["items"]
    assert [(i["kind"], i["due_date"]) for i in items] == [("bill", "2026-10-09")]


def test_paused_recurring_inactive_and_paid_bills_are_not_upcoming(client, db_session, me):
    t, u = me
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    rid = confirm(client, t, "netflix")["id"]
    client.put(f"/api/recurring/{rid}", json={"status": "paused"}, headers=auth(t))
    mk(client, t, name="Off", active=False)
    done = mk(client, t, name="Done", frequency="once")
    pay(client, t, done["id"])
    assert client.get("/api/upcoming", params={"days": 30}, headers=auth(t)).json()["items"] == []


def test_upcoming_empty_and_validation(client, me):
    t, _ = me
    r = client.get("/api/upcoming", headers=auth(t)).json()
    assert r["items"] == [] and all(v == [] for v in r["groups"].values()) and D(r["totals"]["next_7_days"]) == 0
    assert client.get("/api/upcoming", params={"days": 0}, headers=auth(t)).status_code == 422
    assert client.get("/api/upcoming", params={"days": 9999}, headers=auth(t)).status_code == 422


def test_group_boundaries_follow_the_users_timezone(client, db_session, freeze):
    freeze("2026-09-30T19:00:00+00:00")  # 1 Oct 00:30 in India, still 30 Sep in UTC
    t = register(client, "a@example.com")
    u = user_by_email(db_session)
    mk(client, t, name="Due Oct 1", due_date="2026-10-01", frequency="once")
    assert client.get("/api/upcoming", headers=auth(t)).json()["groups"]["today"][0]["name"] == "Due Oct 1"
    u.timezone = "UTC"
    db_session.commit()
    assert client.get("/api/upcoming", headers=auth(t)).json()["groups"]["tomorrow"][0]["name"] == "Due Oct 1"


# ---------- calendar ----------

@pytest.fixture()
def cal(client, db_session, me):
    t, u = me
    monthly(db_session, u, "Employer", 62000, date(2026, 10, 1), 6, type_="income", category=cat(db_session, u, "Salary", "income"))
    confirm(client, t, "employer", type="income")
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    confirm(client, t, "netflix")
    mk(client, t, name="Electricity", due_date="2026-10-08", amount="1850")
    mk(client, t, name="Rent", due_date="2026-10-11", amount="12000")
    mk(client, t, name="Insurance", kind="insurance", due_date="2026-10-20", amount="18000", frequency="yearly")
    mk(client, t, name="Internet", due_date="2026-11-02", amount="999")   # October's instalment was already paid:
    add_tx(db_session, u, 999, date(2026, 10, 2), "Internet")
    mk(client, t, name="Old bill", due_date="2026-09-28", frequency="once", amount="500")
    db_session.commit()
    return t, u


def month_view(client, t, month=None):
    r = client.get("/api/calendar", params={"month": month} if month else {}, headers=auth(t))
    assert r.status_code == 200, r.text
    return r.json()


def test_calendar_current_month(client, cal):
    t, _ = cal
    c = month_view(client, t)
    assert c["month"] == "2026-10" and len(c["days"]) == 31 and c["today"] == "2026-10-04"
    day = {d["date"]: d for d in c["days"]}
    assert day["2026-10-04"]["is_today"] is True and day["2026-10-05"]["is_today"] is False
    assert [(e["name"], e["kind"], e["status"]) for e in day["2026-10-01"]["events"]] == [("Employer", "income", "received")]
    assert [(e["name"], e["kind"], e["status"]) for e in day["2026-10-02"]["events"]] == [("Internet", "bill", "paid")]
    assert [(e["name"], e["kind"], e["status"]) for e in day["2026-10-08"]["events"]] == [
        ("Electricity", "bill", "scheduled"), ("Netflix", "recurring", "scheduled")]
    assert D(day["2026-10-08"]["outflow_total"]) == 1850 + 649 and D(day["2026-10-01"]["income_total"]) == 62000
    assert [e["name"] for e in day["2026-10-11"]["events"]] == ["Rent"] and [e["name"] for e in day["2026-10-20"]["events"]] == ["Insurance"]
    assert day["2026-10-03"]["events"] == []
    s = c["summary"]
    assert (D(s["income_received"]), D(s["income_expected"]), D(s["paid"]), D(s["scheduled"]), D(s["overdue"])) == (62000, 0, 999, 1850 + 649 + 12000 + 18000, 0)
    assert D(s["estimated_net"]) == 62000 - 999 - 32499


def test_large_scheduled_payments_use_income_based_threshold(client, cal):
    t, _ = cal
    c = month_view(client, t)
    assert D(c["large_threshold"]) == D("15500")  # 25% of 62,000 (average of Jul-Sep income)
    flagged = [e["name"] for d in c["days"] for e in d["events"] if e["large"]]
    assert flagged == ["Insurance"] and c["summary"]["large_count"] == 1  # Rent (12,000) is below the threshold


def test_calendar_past_month_shows_actuals_and_overdue(client, cal):
    t, _ = cal
    c = month_view(client, t, "2026-09")
    day = {d["date"]: d for d in c["days"]}
    assert [(e["name"], e["status"]) for e in day["2026-09-28"]["events"]] == [("Old bill", "overdue")]
    assert any(e["name"] == "Netflix" and e["status"] == "paid" and e["kind"] == "recurring" for e in day["2026-09-08"]["events"])
    assert any(e["name"] == "Employer" and e["status"] == "received" for e in day["2026-09-01"]["events"])
    assert D(c["summary"]["overdue"]) == 500


def test_calendar_future_month_projects_expected_income_and_repeats(client, cal):
    t, _ = cal
    c = month_view(client, t, "2026-11")
    day = {d["date"]: d for d in c["days"]}
    assert [(e["name"], e["status"]) for e in day["2026-11-01"]["events"]] == [("Employer", "expected")]
    assert [e["name"] for e in day["2026-11-02"]["events"]] == ["Internet"]
    assert sorted(e["name"] for e in day["2026-11-08"]["events"]) == ["Electricity", "Netflix"]
    assert [e["name"] for e in day["2026-11-11"]["events"]] == ["Rent"]
    assert D(c["summary"]["income_expected"]) == 62000 and D(c["summary"]["income_received"]) == 0


def test_paying_a_bill_moves_it_on_the_calendar(client, cal):
    t, _ = cal
    rent = next(b for b in client.get("/api/bills", headers=auth(t)).json()["items"] if b["name"] == "Rent")
    pay(client, t, rent["id"], payment_method="net_banking")
    day = {d["date"]: d for d in month_view(client, t)["days"]}
    assert [(e["name"], e["status"]) for e in day["2026-10-04"]["events"]] == [("Rent", "paid")]  # paid today
    assert day["2026-10-11"]["events"] == []
    assert [e["name"] for d in month_view(client, t, "2026-11")["days"] for e in d["events"] if e["name"] == "Rent"] == ["Rent"]


def test_calendar_validation_and_empty_state(client, me):
    t, _ = me
    for bad in ("2026-13", "2026-00", "abc", "1999-01", "2026-1", "2026-10-01"):
        assert client.get("/api/calendar", params={"month": bad}, headers=auth(t)).status_code == 422, bad
    c = month_view(client, t)
    assert all(d["events"] == [] for d in c["days"]) and c["large_threshold"] is None
    assert D(c["summary"]["estimated_net"]) == 0 and c["summary"]["large_count"] == 0
    assert len(month_view(client, t, "2028-02")["days"]) == 29  # leap year


def test_future_dated_income_is_expected_not_received(client, db_session, me):
    t, u = me
    add_tx(db_session, u, 5000, date(2026, 10, 25), "Freelance client", "income")
    db_session.commit()
    ev = next(e for d in month_view(client, t)["days"] for e in d["events"] if e["name"] == "Freelance client")
    assert ev["status"] == "expected" and ev["kind"] == "income"


def test_default_calendar_month_follows_users_timezone(client, db_session, freeze):
    freeze("2026-09-30T19:00:00+00:00")
    t = register(client, "a@example.com")
    assert month_view(client, t)["month"] == "2026-10"
    user_by_email(db_session).timezone = "UTC"
    db_session.commit()
    assert month_view(client, t)["month"] == "2026-09"


# ---------- isolation ----------

def test_bills_isolated_between_users(client, db_session, me):
    ta, ua = me
    bill = mk(client, ta, name="A's rent", due_date="2026-10-05")
    a_cat = cat(db_session, ua, "Bills")
    client.cookies.clear()
    tb = register(client, "b@example.com")
    assert client.get("/api/bills", headers=auth(tb)).json()["items"] == []
    assert client.get(f"/api/bills/{bill['id']}", headers=auth(tb)).status_code == 404
    body = {"name": "x", "amount": "1", "due_date": "2026-10-08"}
    assert client.put(f"/api/bills/{bill['id']}", json=body, headers=auth(tb)).status_code == 404
    assert client.delete(f"/api/bills/{bill['id']}", headers=auth(tb)).status_code == 404
    assert pay(client, tb, bill["id"]).status_code == 404
    assert client.post("/api/bills", json={**body, "category_id": a_cat.id}, headers=auth(tb)).status_code == 422
    assert client.get("/api/upcoming", headers=auth(tb)).json()["items"] == []
    assert all(d["events"] == [] for d in month_view(client, tb)["days"])
    assert client.get(f"/api/bills/{bill['id']}", headers=auth(ta)).json()["status"] == "upcoming"  # A untouched
    assert db_session.query(Transaction).filter(Transaction.source == "bill").count() == 0


def test_bills_require_auth(client):
    for path in ("/api/bills", "/api/upcoming", "/api/calendar"):
        assert client.get(path).status_code == 401


def test_large_flag_is_only_for_money_still_to_leave(client, cal):
    t, _ = cal
    ins = next(b for b in client.get("/api/bills", headers=auth(t)).json()["items"] if b["name"] == "Insurance")
    assert pay(client, t, ins["id"]).status_code == 200  # 18,000 is above the 15,500 threshold, but now it is paid
    c = month_view(client, t)
    today_events = {d["date"]: d for d in c["days"]}["2026-10-04"]["events"]
    assert [(e["name"], e["status"], e["large"]) for e in today_events] == [("Insurance", "paid", False)]
    assert c["summary"]["large_count"] == 0 and D(c["summary"]["paid"]) == 999 + 18000
