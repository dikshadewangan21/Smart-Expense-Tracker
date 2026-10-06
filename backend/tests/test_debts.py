"""Debts. Expected values are worked out by hand; clock frozen at Sun 2026-10-04 (IST)."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.core import Bill, Debt, DebtPayment, Transaction
from app.services.debts import next_due, simulate_payoff
from tests.conftest import auth, register
from tests.helpers import add_tx, cat, user_by_email


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def t(client, freeze):
    return register(client, "a@example.com")


def mk(client, t, **over):
    body = {"name": "HDFC Laptop Loan", "kind": "personal", "principal": "100000", "remaining": "45000",
            "interest_rate": "11.5", "emi": "5000", "due_day": 20}
    body.update(over)
    r = client.post("/api/debts", json=body, headers=auth(t))
    assert r.status_code == 201, r.text
    return r.json()


def pay(client, t, did, **body):
    return client.post(f"/api/debts/{did}/payments", json=body, headers=auth(t))


# ---------- pure arithmetic ----------

def test_payoff_simulation_matches_the_hand_worked_schedule():
    r = simulate_payoff(D(1200), D(12), D(500), date(2026, 10, 20), 20)
    # m1: 1200 + 12.00 - 500 = 712.00 | m2: 712 + 7.12 - 500 = 219.12 | m3: 219.12 + 2.19 = 221.31, paid off
    assert r["months"] == 3 and r["total_interest"] == D("21.31") and r["total_paid"] == D("1221.31")
    assert r["payoff_date"] == date(2026, 12, 20)


def test_payoff_without_interest_is_a_simple_division():
    r = simulate_payoff(D(1000), None, D(300), date(2026, 10, 20), 20)
    assert r["months"] == 4 and r["total_interest"] == 0 and r["total_paid"] == 1000   # 300+300+300+100
    assert r["payoff_date"] == date(2027, 1, 20)


def test_emi_that_does_not_cover_interest_gives_no_date_and_says_why():
    r = simulate_payoff(D(100000), D(12), D(1000), date(2026, 10, 20), 20)   # interest 1000.00 == EMI
    assert "payoff_date" not in r and "never reach zero" in r["reason"]
    assert "Add an EMI" in simulate_payoff(D(1000), D(10), None, date(2026, 10, 20), 20)["reason"]
    assert "50 years" in simulate_payoff(D(10_000_000), D("0.5"), D(4200), date(2026, 10, 20), 20)["reason"]


def test_next_due_clamps_to_month_end_and_rolls_over():
    def debt(day):
        return Debt(name="d", kind="personal", principal=1, remaining=1, due_day=day)
    assert next_due(debt(31), date(2026, 10, 4)) == date(2026, 10, 31)
    assert next_due(debt(3), date(2026, 10, 4)) == date(2026, 11, 3)
    assert next_due(debt(4), date(2026, 10, 4)) == date(2026, 10, 4)          # due today counts
    assert next_due(debt(31), date(2027, 2, 10)) == date(2027, 2, 28)
    assert next_due(debt(5), date(2027, 1, 31)) == date(2027, 2, 5)
    assert next_due(debt(5), date(2026, 12, 20)) == date(2027, 1, 5)
    assert next_due(Debt(name="d", kind="personal", principal=1, remaining=0, due_day=5), date(2026, 10, 4)) is None


# ---------- CRUD and views ----------

def test_view_shows_progress_payoff_and_next_due(client, t):
    d = mk(client, t)
    assert d["progress_percent"] == 55.0 and d["direction"] == "owed" and not d["paid_off"]
    assert d["next_due_date"] == "2026-10-20" and d["days_until_due"] == 16
    p = d["payoff"]
    assert p["months"] == 10 and p["payoff_date"] == "2027-07-20" and D(p["total_interest"]) > 0   # 45000 at 11.5%/yr, 5000 on the 20th: first payment 2026-10-20, tenth 2027-07-20


def test_remaining_defaults_to_principal_and_validation(client, t):
    d = mk(client, t, remaining=None)
    assert D(d["remaining"]) == 100000 and d["progress_percent"] == 0.0
    h = auth(t)
    base = {"name": "x", "kind": "personal", "principal": "100"}
    for bad in ({"principal": "0"}, {"interest_rate": "101"}, {"interest_rate": "-1"}, {"emi": "0"}, {"due_day": 32},
                {"due_day": 0}, {"kind": "mortgage"}, {"start_date": "2026-10-05"}, {"remaining": "-1"}, {"name": " "}):
        assert client.post("/api/debts", json={**base, **bad}, headers=h).status_code == 422, bad


def test_progress_never_goes_negative_when_interest_pushed_the_balance_above_the_principal(client, t):
    d = mk(client, t, name="Card", kind="credit_card", principal="20000", remaining="25000")
    assert d["progress_percent"] == 0.0


def test_put_corrects_the_balance(client, t):
    d = mk(client, t)
    body = {"name": "HDFC Loan", "kind": "personal", "principal": "100000", "remaining": "40000", "interest_rate": "11.5", "emi": "5000", "due_day": 20}
    r = client.put(f"/api/debts/{d['id']}", json=body, headers=auth(t))
    assert r.status_code == 200 and D(r.json()["remaining"]) == 40000 and r.json()["progress_percent"] == 60.0


def test_list_sorting_and_summary(client, t, db_session):
    u = user_by_email(db_session)
    for m in (7, 8, 9):                                    # three completed months of 60,000 income
        add_tx(db_session, u, 60000, date(2026, m, 1), "Acme", "income")
    db_session.commit()
    a = mk(client, t, name="A card", kind="credit_card", principal="20000", remaining="20000", interest_rate="36", emi="2000", due_day=25)
    b = mk(client, t, name="B loan", remaining="45000")
    c = mk(client, t, name="C lent", kind="lent", principal="8000", remaining="8000", interest_rate=None, emi=None, due_day=None)
    done = mk(client, t, name="D done", principal="1000", remaining="0", due_day=None, emi=None, interest_rate=None)
    def names(sort):
        return [x["name"] for x in client.get(f"/api/debts?sort={sort}", headers=auth(t)).json()["items"]]
    assert names("due") == ["B loan", "A card", "C lent", "D done"]       # due 20th, 25th, no date; paid-off last
    assert names("remaining") == ["B loan", "A card", "C lent", "D done"]
    assert names("rate") == ["A card", "B loan", "C lent", "D done"]
    assert names("name") == ["A card", "B loan", "C lent", "D done"]
    s = client.get("/api/debts", headers=auth(t)).json()["summary"]
    assert D(s["total_owed"]) == 65000 and D(s["total_lent"]) == 8000 and D(s["monthly_emi"]) == 7000   # 45000+20000 ; 5000+2000
    assert round(s["debt_to_income_percent"], 2) == round(7000 / 60000 * 100, 2)
    assert s["active"] == 3 and s["paid_off"] == 1 and a and b and c and done


# ---------- payments ----------

def test_payment_splits_interest_updates_balance_and_records_the_expense(client, t, db_session):
    d = mk(client, t)
    r = pay(client, t, d["id"], amount="5000", paid_on="2026-10-03", payment_method="upi")
    assert r.status_code == 201, r.text
    body = r.json()
    # interest = 45000 * 11.5 / 1200 = 431.25 ; principal = 5000 - 431.25 = 4568.75 ; remaining = 40431.25
    assert D(body["remaining"]) == D("40431.25") and D(body["interest_paid_total"]) == D("431.25")
    assert D(body["principal_paid_total"]) == D("4568.75") and body["payments_count"] == 1
    p = body["payments"][0]
    assert D(p["interest_paid"]) == D("431.25") and p["transaction_id"] is not None
    tx = db_session.get(Transaction, p["transaction_id"])
    assert tx.type == "expense" and D(tx.amount) == 5000 and tx.merchant == "HDFC Laptop Loan" and tx.source == "debt"
    assert tx.category_id == cat(db_session, user_by_email(db_session), "EMI & Loans").id and tx.date == date(2026, 10, 3)


def test_payment_can_override_the_principal_part_and_skip_the_expense(client, t, db_session):
    d = mk(client, t)
    r = pay(client, t, d["id"], amount="5000", principal_paid="4000", create_transaction=False)
    assert D(r.json()["remaining"]) == 41000 and D(r.json()["interest_paid_total"]) == 1000
    assert r.json()["payments"][0]["transaction_id"] is None and db_session.query(Transaction).count() == 0
    assert pay(client, t, d["id"], amount="100", principal_paid="101").status_code == 422     # principal > payment
    assert pay(client, t, d["id"], amount="50000", principal_paid="50000").status_code == 422  # more than remains


def test_overpaying_is_rejected_but_the_final_payment_with_interest_is_allowed(client, t):
    nr = mk(client, t, name="No rate", remaining="1000", principal="1000", interest_rate=None, emi=None)
    assert pay(client, t, nr["id"], amount="1500").status_code == 422
    wr = mk(client, t, name="With rate", remaining="1000", principal="1000", interest_rate="12")
    assert pay(client, t, wr["id"], amount="1020").status_code == 422        # interest is only 10.00
    r = pay(client, t, wr["id"], amount="1010")                               # 1000 principal + 10.00 interest
    assert r.status_code == 201 and D(r.json()["remaining"]) == 0 and r.json()["paid_off"] is True
    assert r.json()["payoff"] is None and r.json()["progress_percent"] == 100.0
    assert pay(client, t, wr["id"], amount="10").status_code == 422           # already paid off


def test_repayment_of_money_you_lent_is_not_income(client, t, db_session):
    d = mk(client, t, name="Ravi", kind="lent", principal="8000", remaining="8000", interest_rate=None, emi=None, due_day=None)
    assert d["direction"] == "lent" and d["payoff"] is None
    r = pay(client, t, d["id"], amount="3000")
    assert r.status_code == 201 and D(r.json()["remaining"]) == 5000 and db_session.query(Transaction).count() == 0
    r = pay(client, t, d["id"], amount="1000", create_transaction=True)
    assert r.status_code == 422 and "not income" in r.json()["detail"]


def test_future_payment_date_and_foreign_account_are_rejected(client, t, db_session):
    d = mk(client, t)
    assert pay(client, t, d["id"], amount="100", paid_on="2026-10-05").status_code == 422
    client.cookies.clear()
    b = register(client, "b@example.com")
    acc = client.post("/api/accounts", json={"name": "B bank", "kind": "bank"}, headers=auth(b)).json()
    assert pay(client, t, d["id"], amount="100", account_id=acc["id"]).status_code == 422


def test_deleting_a_payment_restores_the_balance_and_keeps_the_expense(client, t, db_session):
    d = mk(client, t)
    body = pay(client, t, d["id"], amount="5000").json()
    pid = body["payments"][0]["id"]
    r = client.delete(f"/api/debts/{d['id']}/payments/{pid}", headers=auth(t))
    assert r.status_code == 200 and D(r.json()["remaining"]) == 45000 and r.json()["payments_count"] == 0
    assert db_session.query(Transaction).count() == 1                          # the user's expense is not deleted behind their back
    assert client.delete(f"/api/debts/{d['id']}/payments/{pid}", headers=auth(t)).status_code == 404


# ---------- linking a bill ----------

def _bill(client, t, **over):
    body = {"name": "HDFC Laptop EMI", "kind": "emi", "amount": "5000", "due_date": "2026-10-20", "frequency": "monthly"}
    body.update(over)
    r = client.post("/api/bills", json=body, headers=auth(t))
    assert r.status_code == 201, r.text
    return r.json()


def test_paying_a_linked_bill_also_pays_down_the_debt_once(client, t, db_session):
    bill = _bill(client, t)
    d = mk(client, t, bill_id=bill["id"])
    assert d["bill_name"] == "HDFC Laptop EMI"
    r = client.post(f"/api/bills/{bill['id']}/pay", json={"create_transaction": True}, headers=auth(t))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["debt_id"] == d["id"] and D(out["debt_remaining"]) == D("40431.25")
    assert db_session.query(Transaction).count() == 1                          # one expense, not two
    pay_row = db_session.query(DebtPayment).one()
    assert pay_row.transaction_id == out["transaction_id"] and D(pay_row.principal_paid) == D("4568.75")


def test_bill_payment_never_fails_because_the_debt_is_already_cleared(client, t, db_session):
    bill = _bill(client, t)
    mk(client, t, bill_id=bill["id"], remaining="0")
    r = client.post(f"/api/bills/{bill['id']}/pay", json={"create_transaction": False}, headers=auth(t))
    assert r.status_code == 200 and db_session.query(DebtPayment).count() == 0


def test_bill_link_rules(client, t, db_session):
    bill = _bill(client, t)
    mk(client, t, bill_id=bill["id"])
    r = client.post("/api/debts", json={"name": "Other", "kind": "personal", "principal": "10", "bill_id": bill["id"]}, headers=auth(t))
    assert r.status_code == 422 and "already linked" in r.json()["detail"]
    client.cookies.clear()
    b = register(client, "b@example.com")
    r = client.post("/api/debts", json={"name": "Mine", "kind": "personal", "principal": "10", "bill_id": bill["id"]}, headers=auth(b))
    assert r.status_code == 422                                                # someone else's bill
    client.cookies.clear()
    # deleting the bill unlinks the debt instead of deleting it
    db_session.query(Bill).filter(Bill.id == bill["id"]).delete()
    db_session.commit()
    assert db_session.query(Debt).filter(Debt.name == "HDFC Laptop Loan").one().bill_id is None


# ---------- health score ----------

def _health(client, t, key):
    comps = client.get("/api/dashboard", headers=auth(t)).json()["financial_health"]["components"]
    return next(c for c in comps if c["key"] == key)


def test_emi_is_not_counted_twice_in_the_health_score(client, t, db_session):
    u = user_by_email(db_session)
    add_tx(db_session, u, 50000, date(2026, 10, 1), "Acme", "income")
    db_session.commit()
    bill = _bill(client, t)
    mk(client, t)
    assert _health(client, t, "recurring_load")["value"] == 10.0               # 5000 / 50000: bill counted
    assert _health(client, t, "debt_burden")["value"] == 10.0
    client.put(f"/api/debts/{client.get('/api/debts', headers=auth(t)).json()['items'][0]['id']}",
               json={"name": "HDFC Laptop Loan", "kind": "personal", "principal": "100000", "remaining": "45000",
                     "interest_rate": "11.5", "emi": "5000", "due_day": 20, "bill_id": bill["id"]}, headers=auth(t))
    assert _health(client, t, "recurring_load")["value"] == 0.0                # linked: counted once, as debt burden
    assert _health(client, t, "debt_burden")["value"] == 10.0


def test_a_paid_off_debt_stops_counting_towards_debt_burden(client, t, db_session):
    u = user_by_email(db_session)
    add_tx(db_session, u, 50000, date(2026, 10, 1), "Acme", "income")
    db_session.commit()
    d = mk(client, t, remaining="0")
    assert _health(client, t, "debt_burden")["value"] == 0.0 and d


# ---------- isolation ----------

def test_users_cannot_touch_each_others_debts(client, t):
    d = mk(client, t)
    p = pay(client, t, d["id"], amount="5000").json()["payments"][0]["id"]
    client.cookies.clear()
    b = register(client, "b@example.com")
    h = auth(b)
    assert client.get("/api/debts", headers=h).json()["items"] == []
    assert client.get(f"/api/debts/{d['id']}", headers=h).status_code == 404
    assert client.delete(f"/api/debts/{d['id']}", headers=h).status_code == 404
    assert pay(client, b, d["id"], amount="1").status_code == 404
    assert client.delete(f"/api/debts/{d['id']}/payments/{p}", headers=h).status_code == 404
    assert D(client.get(f"/api/debts/{d['id']}", headers=auth(t)).json()["remaining"]) == D("40431.25")
