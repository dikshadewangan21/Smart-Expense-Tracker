"""Net worth, accounts, valuations and transfers. The scenario's totals are worked out by hand in the comments.
Clock frozen at Sun 2026-10-04 (IST)."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.core import Account, Debt, DebtPayment, Transaction
from tests.conftest import auth, register
from tests.helpers import user_by_email


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def t(client, freeze):
    return register(client, "a@example.com")


def acct(db, u, name, kind, opening=0, archived=False):
    a = Account(user_id=u.id, name=name, kind=kind, opening_balance=Decimal(str(opening)), archived=archived)
    db.add(a)
    db.flush()
    return a


def tx(db, u, type_, amount, d, account=None, to=None, currency=None):
    row = Transaction(user_id=u.id, type=type_, amount=Decimal(str(amount)), date=d, currency=currency or u.currency,
                      account_id=account.id if account else None, to_account_id=to.id if to else None)
    db.add(row)
    db.flush()
    return row


@pytest.fixture()
def world(client, db_session, t):
    u = user_by_email(db_session)
    w = {"u": u}
    w["bank"] = acct(db_session, u, "Bank", "bank", 10000)
    w["cash"] = acct(db_session, u, "Cash", "cash", 500)
    w["card"] = acct(db_session, u, "Card", "credit_card", 0)
    w["inv"] = acct(db_session, u, "Funds", "investment", 0)
    w["flat"] = acct(db_session, u, "Flat", "property", 2_000_000)
    w["od"] = acct(db_session, u, "Overdraft", "bank", 0)
    b, c, k, i, o = w["bank"], w["cash"], w["card"], w["inv"], w["od"]
    tx(db_session, u, "expense", 200, date(2026, 8, 15), b)
    tx(db_session, u, "income", 50000, date(2026, 9, 1), b)
    tx(db_session, u, "expense", 8000, date(2026, 9, 10), b)
    tx(db_session, u, "expense", 3000, date(2026, 9, 15), k)
    tx(db_session, u, "transfer", 2000, date(2026, 9, 20), b, k)           # pay the card from the bank
    tx(db_session, u, "expense", 400, date(2026, 9, 25), o)
    tx(db_session, u, "expense", 300, date(2026, 10, 2), c)
    tx(db_session, u, "transfer", 5000, date(2026, 10, 3), b, i)           # bank -> funds
    tx(db_session, u, "expense", 9999, date(2026, 10, 10), b)              # future: must not count yet
    tx(db_session, u, "expense", 700, date(2026, 9, 12))                   # no account
    tx(db_session, u, "expense", 50, date(2026, 9, 5), b, currency="USD")  # other currency
    tx(db_session, u, "transfer", 77777, date(2026, 9, 6), b)              # legacy transfer without destination: ignored
    w["loan"] = Debt(user_id=u.id, name="Loan", kind="personal", principal=100000, remaining=90000, start_date=date(2026, 1, 1))
    w["newloan"] = Debt(user_id=u.id, name="New loan", kind="borrowed", principal=10000, remaining=10000, start_date=date(2026, 9, 15))
    w["lent"] = Debt(user_id=u.id, name="Ravi", kind="lent", principal=3000, remaining=3000)
    db_session.add_all([w["loan"], w["newloan"], w["lent"]])
    db_session.flush()
    db_session.add(DebtPayment(debt_id=w["loan"].id, amount=5000, principal_paid=5000, date=date(2026, 10, 2)))
    db_session.commit()
    for d, v in (("2026-08-31", "20000"), ("2026-10-01", "26000")):
        r = client.post(f"/api/accounts/{i.id}/valuations", json={"date": d, "value": v}, headers=auth(t))
        assert r.status_code == 201, r.text
    return w


def nw(client, t, **params):
    r = client.get("/api/net-worth", params=params, headers=auth(t))
    assert r.status_code == 200, r.text
    return r.json()


def test_net_worth_today_matches_the_hand_computed_total(client, world, t):
    n = nw(client, t, months=3)
    by = {a["name"]: D(a["balance"]) for a in n["accounts"]}
    # Bank: 10000 -200 +50000 -8000 -2000 (to card) -5000 (to funds) = 44800  (USD, future and destination-less rows ignored)
    # Cash 500-300 = 200 | Card 0 -3000 +2000 = -1000 | Funds: 26000 valuation (Oct 1) + 5000 transferred in after = 31000
    # Flat 2,000,000 | Overdraft -400
    assert by == {"Bank": 44800, "Cash": 200, "Card": -1000, "Funds": 31000, "Flat": 2_000_000, "Overdraft": -400}
    # assets 44800+200+31000+2,000,000+3000 (lent) = 2,079,000 ; liabilities card 1000 + overdraft 400 + loans 90000+10000
    assert D(n["assets"]) == 2_079_000 and D(n["liabilities"]) == 101_400 and D(n["net_worth"]) == 1_977_600


def test_breakdown_follows_the_spec_categories(client, world, t):
    n = nw(client, t)
    a = {x["key"]: D(x["amount"]) for x in n["assets_breakdown"]}
    l = {x["key"]: D(x["amount"]) for x in n["liabilities_breakdown"]}
    assert a == {"cash": 200, "bank": 44800, "investments": 31000, "property": 2_000_000, "lent": 3000}
    assert l == {"loans": 100_000, "credit_card": 1000, "other_debt": 400}
    assert {i["name"] for i in next(x for x in n["liabilities_breakdown"] if x["key"] == "loans")["items"]} == {"Loan", "New loan"}


def test_trend_is_rebuilt_from_history_not_stored_snapshots(client, world, t):
    n = nw(client, t, months=3)
    pts = {p["date"]: p for p in n["trend"]}
    assert list(pts) == ["2026-07-31", "2026-08-31", "2026-09-30", "2026-10-04"] and n["trend"][-1]["label"] == "Today"
    # Aug 31: bank 10000-200 = 9800, cash 500, card 0, funds 20000 (valuation dated Aug 31 counts), flat 2,000,000, lent 3000
    #   -> assets 2,033,300 ; liabilities: loan 90000 + 5000 paid on Oct 2 = 95000 ('New loan' began Sep 15: not yet)
    assert D(pts["2026-08-31"]["assets"]) == 2_033_300 and D(pts["2026-08-31"]["liabilities"]) == 95_000
    assert D(pts["2026-08-31"]["net_worth"]) == 1_938_300
    # Sep 30: bank 49800 (Oct 3 transfer not yet), cash 500, card -1000, funds 20000 (Oct 1 valuation not yet), overdraft -400
    #   assets 49800+500+20000+2,000,000+3000 = 2,073,300 ; liabilities 1000+400+95000+10000 = 106,400
    assert D(pts["2026-09-30"]["assets"]) == 2_073_300 and D(pts["2026-09-30"]["liabilities"]) == 106_400
    assert D(pts["2026-09-30"]["net_worth"]) == 1_966_900
    assert D(pts["2026-10-04"]["net_worth"]) == 1_977_600


def test_change_since_a_month_ago_adds_up(client, world, t):
    c = nw(client, t)["change"]
    # on Sep 4: bank 59800, cash 500, funds 20000, flat 2,000,000, lent 3000 = 2,083,300 ; liabilities loan 95000
    assert c["compared_to"] == "2026-09-04"
    assert D(c["net_worth"]) == -10_700 and D(c["assets"]) == -4_300 and D(c["liabilities"]) == 6_400
    assert D(c["assets"]) - D(c["liabilities"]) == D(c["net_worth"])


def test_the_honest_notes(client, world, t):
    n = nw(client, t)
    assert n["unassigned"] == {"count": 1, "net": -700}
    assert n["excluded_other_currency"] == 1
    assert any("not linked to an account" in x for x in n["notes"]) and any("another currency" in x for x in n["notes"])


def test_goals_are_not_double_counted(client, world, t):
    before = nw(client, t)["net_worth"]
    client.post("/api/goals", json={"name": "Holiday", "target_amount": "50000", "current_amount": "40000"}, headers=auth(t))
    assert nw(client, t)["net_worth"] == before


def test_dashboard_uses_the_same_numbers(client, world, t):
    d = client.get("/api/dashboard", headers=auth(t)).json()
    assert D(d["cards"]["net_worth"]) == 1_977_600
    assert D(d["net_worth_detail"]["assets"]) == 2_079_000 and D(d["net_worth_detail"]["liabilities"]) == 101_400


def test_archived_accounts_leave_net_worth_and_can_come_back(client, world, t):
    flat = world["flat"].id
    assert client.put(f"/api/accounts/{flat}", json={"archived": True}, headers=auth(t)).status_code == 200
    assert D(nw(client, t)["assets"]) == 79_000
    assert flat not in [a["id"] for a in client.get("/api/accounts", headers=auth(t)).json()]
    assert flat in [a["id"] for a in client.get("/api/accounts?include_archived=true", headers=auth(t)).json()]
    client.put(f"/api/accounts/{flat}", json={"archived": False}, headers=auth(t))
    assert D(nw(client, t)["assets"]) == 2_079_000


def test_valuation_replaces_the_base_and_later_transactions_stack_on_top(client, world, t):
    inv = world["inv"].id
    r = client.post(f"/api/accounts/{inv}/valuations", json={"date": "2026-10-04", "value": "40000", "note": "NAV"}, headers=auth(t))
    assert r.status_code == 201
    funds = next(a for a in nw(client, t)["accounts"] if a["name"] == "Funds")
    assert D(funds["balance"]) == 40000 and funds["valued_on"] == "2026-10-04"       # Oct 3 transfer is before this valuation
    # same date again replaces, it does not duplicate
    client.post(f"/api/accounts/{inv}/valuations", json={"date": "2026-10-04", "value": "41000"}, headers=auth(t))
    vals = client.get(f"/api/accounts/{inv}/valuations", headers=auth(t)).json()
    assert [v["date"] for v in vals] == ["2026-10-04", "2026-10-01", "2026-08-31"] and D(vals[0]["value"]) == 41000
    assert client.post(f"/api/accounts/{inv}/valuations", json={"date": "2026-10-05", "value": "1"}, headers=auth(t)).status_code == 422
    assert client.delete(f"/api/accounts/{inv}/valuations/{vals[0]['id']}", headers=auth(t)).status_code == 204
    funds = next(a for a in nw(client, t)["accounts"] if a["name"] == "Funds")
    assert D(funds["balance"]) == 31000


def test_account_edit_changes_balance_via_the_opening_balance(client, world, t):
    r = client.put(f"/api/accounts/{world['cash'].id}", json={"name": " Wallet  cash ", "opening_balance": "1500", "kind": "wallet"}, headers=auth(t))
    assert r.status_code == 200 and r.json()["name"] == "Wallet cash"
    cash = next(a for a in nw(client, t)["accounts"] if a["id"] == world["cash"].id)
    assert D(cash["balance"]) == 1200                                                # 1500 - 300
    assert client.put(f"/api/accounts/{world['cash'].id}", json={"kind": "boat"}, headers=auth(t)).status_code == 422


def test_empty_user_gets_zeroes_and_an_empty_but_valid_trend(client, t):
    n = nw(client, t, months=2)
    assert n["net_worth"] == 0 and n["accounts"] == [] and n["assets_breakdown"] == [] and len(n["trend"]) == 3
    assert client.get("/api/net-worth?months=0", headers=auth(t)).status_code == 422
    assert client.get("/api/net-worth?months=61", headers=auth(t)).status_code == 422


def test_a_credit_card_in_credit_is_an_asset(client, db_session, t):
    u = user_by_email(db_session)
    k = acct(db_session, u, "Card", "credit_card", 0)
    tx(db_session, u, "income", 500, date(2026, 9, 1), k)                            # refund bigger than the balance
    db_session.commit()
    n = nw(client, t)
    assert D(n["assets"]) == 500 and D(n["liabilities"]) == 0
    assert n["assets_breakdown"][0]["key"] == "other_assets"


def test_credit_card_debt_kind_is_a_credit_card_liability(client, db_session, t):
    u = user_by_email(db_session)
    db_session.add(Debt(user_id=u.id, name="Old card", kind="credit_card", principal=7000, remaining=6000))
    db_session.commit()
    l = {x["key"]: D(x["amount"]) for x in nw(client, t)["liabilities_breakdown"]}
    assert l == {"credit_card": 6000}


def test_users_see_only_their_own_accounts_and_valuations(client, world, t):
    inv = world["inv"].id
    client.cookies.clear()
    b = register(client, "b@example.com")
    h = auth(b)
    assert nw(client, b)["accounts"] == [] and nw(client, b)["net_worth"] == 0
    assert client.put(f"/api/accounts/{inv}", json={"name": "x"}, headers=h).status_code == 404
    assert client.get(f"/api/accounts/{inv}/valuations", headers=h).status_code == 404
    assert client.post(f"/api/accounts/{inv}/valuations", json={"date": "2026-10-01", "value": "1"}, headers=h).status_code == 404
    vid = client.get(f"/api/accounts/{inv}/valuations", headers=auth(t)).json()[0]["id"]
    assert client.delete(f"/api/accounts/{inv}/valuations/{vid}", headers=h).status_code == 404


# ---------- transfers through the transaction API ----------

def test_transfer_api_rules(client, db_session, t):
    h = auth(t)
    a = client.post("/api/accounts", json={"name": "A", "kind": "bank", "opening_balance": "1000"}, headers=h).json()
    b = client.post("/api/accounts", json={"name": "B", "kind": "cash"}, headers=h).json()
    body = {"type": "transfer", "amount": "250", "date": "2026-10-03", "account_id": a["id"], "to_account_id": b["id"], "merchant": "Netflix"}
    r = client.post("/api/transactions", json=body, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["to_account_id"] == b["id"] and r.json()["category_id"] is None   # no auto-category for a transfer
    bal = {x["name"]: D(x["balance"]) for x in nw(client, t)["accounts"]}
    assert bal == {"A": 750, "B": 250} and D(nw(client, t)["net_worth"]) == 1000      # moving money doesn't change net worth
    for bad in ({"to_account_id": None}, {"to_account_id": a["id"]}, {"account_id": None}, {"category_id": 1}):
        assert client.post("/api/transactions", json={**body, **bad}, headers=h).status_code == 422, bad
    exp = {"type": "expense", "amount": "5", "date": "2026-10-03", "account_id": a["id"], "to_account_id": b["id"]}
    assert client.post("/api/transactions", json=exp, headers=h).status_code == 422   # only transfers have a destination
    # filtering by an account finds transfers in either direction
    for acc in (a, b):
        got = client.get(f"/api/transactions?account_id={acc['id']}", headers=h).json()
        assert got["total"] == 1 and got["items"][0]["type"] == "transfer"
    # duplicate keeps the destination; editing into a plain expense clears it
    dup = client.post(f"/api/transactions/{r.json()['id']}/duplicate", headers=h).json()
    assert dup["to_account_id"] == b["id"]
    upd = client.put(f"/api/transactions/{dup['id']}", json={"type": "expense", "amount": "5", "date": "2026-10-03", "account_id": a["id"]}, headers=h)
    assert upd.status_code == 200 and upd.json()["to_account_id"] is None


def test_cannot_transfer_to_someone_elses_account(client, db_session, t):
    other = client.post("/api/accounts", json={"name": "Mine", "kind": "bank"}, headers=auth(t)).json()
    client.cookies.clear()
    b = register(client, "b@example.com")
    theirs = client.post("/api/accounts", json={"name": "Theirs", "kind": "bank"}, headers=auth(b)).json()
    body = {"type": "transfer", "amount": "10", "date": "2026-10-03", "account_id": other["id"], "to_account_id": theirs["id"]}
    assert client.post("/api/transactions", json=body, headers=auth(t)).status_code == 422


def test_a_transaction_on_the_valuation_date_is_already_inside_the_valuation(client, world, t):
    inv = world["inv"].id
    # the Oct 3 transfer (5000) is on the valuation date, so the 40000 already includes it; nothing is added on top
    client.post(f"/api/accounts/{inv}/valuations", json={"date": "2026-10-03", "value": "40000"}, headers=auth(t))
    assert D(next(a for a in nw(client, t)["accounts"] if a["name"] == "Funds")["balance"]) == 40000


def test_a_debt_payment_on_a_month_end_is_already_reflected_that_day(client, db_session, world, t):
    db_session.add(DebtPayment(debt_id=world["loan"].id, amount=2000, principal_paid=2000, date=date(2026, 9, 30)))
    world["loan"].remaining = 88000                                       # the extra payment brought today's balance down
    db_session.commit()
    pts = {p["date"]: p for p in nw(client, t, months=1)["trend"]}
    # Sep 30: today 88000 + only the Oct 2 payment (5000) added back = 93000 ; 'New loan' 10000 -> liabilities 93000+10000+1000+400
    assert D(pts["2026-09-30"]["liabilities"]) == 104_400


def test_a_debt_that_began_on_a_month_end_counts_that_day(client, db_session, world, t):
    world["newloan"].start_date = date(2026, 8, 31)
    db_session.commit()
    pts = {p["date"]: p for p in nw(client, t, months=2)["trend"]}
    assert D(pts["2026-08-31"]["liabilities"]) == 105_000                  # loan 95000 + new loan 10000
    world["newloan"].start_date = date(2026, 9, 1)
    db_session.commit()
    pts = {p["date"]: p for p in nw(client, t, months=2)["trend"]}
    assert D(pts["2026-08-31"]["liabilities"]) == 95_000


def test_one_month_ago_is_calendar_aware_at_month_ends(client, db_session, freeze, t):
    freeze("2026-10-31T06:00:00+00:00")
    assert nw(client, t)["change"]["compared_to"] == "2026-09-30"          # not Oct 1 (30 days back)
    freeze("2027-03-31T06:00:00+00:00")
    assert nw(client, t)["change"]["compared_to"] == "2027-02-28"
