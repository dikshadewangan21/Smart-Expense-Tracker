from datetime import date, timedelta
from decimal import Decimal

from app.models.core import Bill, Transaction
from app.services import recurring as rec_svc
from app.services.schedule import next_after
from tests.conftest import auth, register
from tests.helpers import add_tx, cat, monthly, user_by_email

TODAY = date(2026, 10, 4)


def setup(client, db, email="a@example.com"):
    token = register(client, email)
    return token, user_by_email(db, email)


def cands(client, token, **params):
    r = client.get("/api/recurring/candidates", params=params, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def by_key(items, key):
    return next((c for c in items if c["merchant_key"] == key), None)


# ---------- detection ----------

def test_monthly_subscription_detected_with_all_fields(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6, category=cat(db_session, u, "Subscriptions"))
    c = by_key(cands(client, t), "netflix")
    assert c["frequency"] == "monthly" and Decimal(str(c["amount"])) == 649
    assert c["category"] == "Subscriptions" and c["occurrences"] == 6 and c["suggested"] is True
    assert c["last_date"] == "2026-09-08" and c["next_expected"] == "2026-10-08"
    assert Decimal(str(c["monthly_equivalent"])) == 649 and Decimal(str(c["annual_cost"])) == 7788
    assert c["confidence"] >= 0.9 and c["amount_varies"] is False and c["reasons"]


def test_weekly_biweekly_quarterly_yearly(client, db_session, freeze):
    t, u = setup(client, db_session)
    for i in range(8):
        add_tx(db_session, u, 100, date(2026, 10, 3) - timedelta(days=7 * i), "Tiffin Service")
    for i in range(6):
        add_tx(db_session, u, 2500, date(2026, 9, 25) - timedelta(days=14 * i), "Cleaner")
    for i in range(4):
        add_tx(db_session, u, 3000, date(2026, 8, 15) - timedelta(days=91 * i), "Water Tanker")
    for i in range(3):
        add_tx(db_session, u, 1499, date(2026, 6, 1) - timedelta(days=365 * i), "Prime Annual")
    db_session.commit()
    got = {c["merchant_key"]: c for c in cands(client, t)}
    assert got["tiffin service"]["frequency"] == "weekly" and got["tiffin service"]["next_expected"] == "2026-10-10"
    assert got["cleaner"]["frequency"] == "biweekly" and got["cleaner"]["next_expected"] == "2026-10-09"
    assert got["water tanker"]["frequency"] == "quarterly"
    assert got["prime annual"]["frequency"] == "yearly" and got["prime annual"]["next_expected"] == "2027-06-01"
    assert Decimal(str(got["tiffin service"]["annual_cost"])) == 5200
    assert Decimal(str(got["cleaner"]["annual_cost"])) == 65000


def test_two_yearly_payments_are_possible_not_suggested(client, db_session, freeze):
    t, u = setup(client, db_session)
    add_tx(db_session, u, 1499, date(2026, 6, 1), "Insurer")
    add_tx(db_session, u, 1499, date(2025, 6, 1), "Insurer")
    db_session.commit()
    assert by_key(cands(client, t), "insurer") is None  # default list: threshold applies
    c = by_key(cands(client, t, include_uncertain=True), "insurer")
    assert c and c["suggested"] is False and c["confidence"] < 0.7


def test_irregular_and_daily_patterns_not_detected(client, db_session, freeze):
    t, u = setup(client, db_session)
    for d in (date(2026, 9, 29), date(2026, 9, 11), date(2026, 8, 20), date(2026, 8, 2), date(2026, 7, 9), date(2026, 6, 1)):
        add_tx(db_session, u, 300, d, "Random Cafe")  # gaps 18, 22, 18, 24, 38: no frequency
    for i in range(12):
        add_tx(db_session, u, 120, TODAY - timedelta(days=i), "Daily Chai")
    db_session.commit()
    keys = {c["merchant_key"] for c in cands(client, t, include_uncertain=True)}
    assert "random cafe" not in keys and "daily chai" not in keys


def test_only_two_monthly_payments_is_not_enough(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "New Gym", 1500, date(2026, 9, 5), 2)
    assert by_key(cands(client, t, include_uncertain=True), "new gym") is None


def test_lapsed_subscription_not_suggested(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Old Service", 199, date(2026, 7, 10), 6)  # last payment 86 days ago (>1.75 months)
    assert by_key(cands(client, t, include_uncertain=True), "old service") is None


def test_varying_amounts_lower_confidence_but_flagged(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Fixed Co", 1000, date(2026, 9, 10), 6)
    for i, amt in enumerate([1600, 1850, 2100, 1700, 1950, 1800]):
        add_tx(db_session, u, amt, date(2026, 9 - i if i < 9 else 1, 10) if 9 - i > 0 else date(2025, 12, 10), "Power Utility")
    db_session.commit()
    items = cands(client, t, include_uncertain=True)
    fixed, power = by_key(items, "fixed co"), by_key(items, "power utility")
    assert fixed and power and power["amount_varies"] is True and fixed["amount_varies"] is False
    assert power["confidence"] < fixed["confidence"]
    assert 1700 <= Decimal(str(power["amount"])) <= 1900  # median of the core amounts


def test_one_off_outlier_amount_is_excluded_from_pattern(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Phone Plan", 399, date(2026, 9, 12), 6)
    add_tx(db_session, u, 24999, date(2026, 8, 20), "Phone Plan")  # a phone purchase at the same merchant
    db_session.commit()
    c = by_key(cands(client, t), "phone plan")
    assert c and Decimal(str(c["amount"])) == 399 and c["occurrences"] == 6


def test_same_day_duplicates_do_not_break_or_inflate(client, db_session, freeze):
    t, u = setup(client, db_session)
    for tx in monthly(db_session, u, "Spotify", 119, date(2026, 9, 15), 6):
        add_tx(db_session, u, 119, tx.date, "Spotify")  # exact duplicate on the same day
    db_session.commit()
    c = by_key(cands(client, t), "spotify")
    assert c and c["frequency"] == "monthly" and c["occurrences"] == 6  # distinct dates, not 12


def test_merchant_name_variants_are_grouped(client, db_session, freeze):
    t, u = setup(client, db_session)
    for i, name in enumerate(["NETFLIX", "netflix ", "Netflix", "NetFlix", "netflix", "Netflix"]):
        add_tx(db_session, u, 649, date(2026, 9, 8) if i == 0 else date(2026, 9 - i, 8) if 9 - i > 0 else date(2026, 1, 8), name)
    db_session.commit()
    c = by_key(cands(client, t), "netflix")
    assert c and c["occurrences"] == 6


def test_confidence_reflects_regularity(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Perfect", 500, date(2026, 9, 5), 6)
    dates = [date(2026, 9, 5), date(2026, 8, 5), date(2026, 6, 5), date(2026, 5, 5), date(2026, 4, 5), date(2026, 3, 5)]  # July missed
    for d in dates:
        add_tx(db_session, u, 500, d, "Gappy")
    db_session.commit()
    items = cands(client, t, include_uncertain=True)
    assert by_key(items, "perfect")["confidence"] > by_key(items, "gappy")["confidence"]


def test_foreign_currency_transactions_ignored(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Overseas SaaS", 20, date(2026, 9, 5), 6, currency="USD")
    assert by_key(cands(client, t, include_uncertain=True), "overseas saas") is None


def test_recurring_income_detected_separately(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Acme Pvt Ltd", 62000, date(2026, 10, 1), 6, type_="income", category=cat(db_session, u, "Salary", "income"))
    assert by_key(cands(client, t, type="income"), "acme pvt ltd")["next_expected"] == "2026-11-01"
    assert by_key(cands(client, t, type="expense"), "acme pvt ltd") is None


def test_merchant_covered_by_a_bill_is_not_suggested(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Airtel Broadband", 999, date(2026, 9, 12), 6)
    assert by_key(cands(client, t), "airtel broadband") is not None
    db_session.add(Bill(user_id=u.id, name="airtel  broadband", amount=Decimal("999"), due_date=date(2026, 10, 12)))
    db_session.commit()
    assert by_key(cands(client, t), "airtel broadband") is None


# ---------- next-payment maths ----------

def test_next_payment_rolls_forward_and_keeps_month_end_anchor():
    assert next_after(date(2026, 8, 5), "monthly", TODAY) == date(2026, 10, 5)
    assert next_after(date(2026, 9, 5), "monthly", date(2026, 10, 5)) == date(2026, 10, 5)   # due today
    assert next_after(date(2026, 10, 5), "monthly", date(2026, 10, 5)) == date(2026, 11, 5)  # already paid today
    assert next_after(date(2026, 1, 31), "monthly", date(2026, 2, 1), 31) == date(2026, 2, 28)
    assert next_after(date(2026, 2, 28), "monthly", date(2026, 3, 1), 31) == date(2026, 3, 31)


def test_expected_date_is_never_in_the_past(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Late Payer", 700, date(2026, 9, 1), 6)  # next would be Oct 1 (already passed)
    c = by_key(cands(client, t), "late payer")
    assert c["next_expected"] == "2026-11-01"


# ---------- confirm / ignore / edit / delete ----------

def test_confirm_creates_reliable_record_and_removes_candidate(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    r = client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(t))
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["status"] == "confirmed" and rec["source"] == "detected" and rec["confidence"] >= 0.9
    assert rec["next_expected"] == "2026-10-08" and rec["days_until_next"] == 4
    assert by_key(cands(client, t), "netflix") is None
    lst = client.get("/api/recurring", headers=auth(t)).json()
    assert [i["merchant"] for i in lst["items"]] == ["Netflix"]
    assert Decimal(str(lst["totals"]["monthly_cost"])) == 649 and Decimal(str(lst["totals"]["annual_cost"])) == 7788
    assert client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(t)).status_code == 404


def test_confirm_with_corrections(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Prime", 1499, date(2026, 9, 3), 6)
    ent = cat(db_session, u, "Entertainment")
    r = client.post("/api/recurring/confirm", headers=auth(t),
                    json={"merchant_key": "prime", "category_id": ent.id, "merchant": "Amazon Prime", "frequency": "quarterly"})
    assert r.status_code == 201
    rec = r.json()
    assert rec["category"] == "Entertainment" and rec["merchant"] == "Amazon Prime" and rec["frequency"] == "quarterly"
    assert Decimal(str(rec["annual_cost"])) == 1499 * 4 and rec["next_expected"] == "2026-12-03"


def test_confirm_rejects_unknown_pattern_and_bad_category(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    assert client.post("/api/recurring/confirm", json={"merchant_key": "nothing"}, headers=auth(t)).status_code == 404
    salary = cat(db_session, u, "Salary", "income")
    assert client.post("/api/recurring/confirm", json={"merchant_key": "netflix", "category_id": salary.id},
                       headers=auth(t)).status_code == 422
    assert client.post("/api/recurring/confirm", json={"merchant_key": "netflix", "category_id": 99999},
                       headers=auth(t)).status_code == 422


def test_ignore_hides_pattern_and_deleting_ignore_restores_it(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Cult Fit", 1500, date(2026, 9, 5), 6)
    r = client.post("/api/recurring/ignore", json={"merchant_key": "cult fit"}, headers=auth(t))
    assert r.status_code == 201 and r.json()["status"] == "ignored"
    assert by_key(cands(client, t), "cult fit") is None
    assert client.get("/api/recurring", headers=auth(t)).json()["items"] == []  # not a confirmed subscription
    ign = client.get("/api/recurring/ignored", headers=auth(t)).json()
    assert [i["merchant"] for i in ign] == ["Cult Fit"]
    assert client.put(f"/api/recurring/{ign[0]['id']}", json={"amount": "1"}, headers=auth(t)).status_code == 409
    assert client.delete(f"/api/recurring/{ign[0]['id']}", headers=auth(t)).status_code == 204
    assert by_key(cands(client, t), "cult fit") is not None


def test_edit_pause_resume_and_clear_category(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6, category=cat(db_session, u, "Subscriptions"))
    rid = client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(t)).json()["id"]
    r = client.put(f"/api/recurring/{rid}", json={"amount": "799", "frequency": "yearly"}, headers=auth(t)).json()
    assert Decimal(str(r["amount"])) == 799 and r["frequency"] == "yearly" and r["category"] == "Subscriptions"
    r = client.put(f"/api/recurring/{rid}", json={"category_id": None}, headers=auth(t)).json()
    assert r["category"] is None  # explicit null clears; omitted leaves untouched
    client.put(f"/api/recurring/{rid}", json={"frequency": "monthly", "amount": "649"}, headers=auth(t))
    r = client.put(f"/api/recurring/{rid}", json={"status": "paused"}, headers=auth(t)).json()
    assert r["status"] == "paused"
    lst = client.get("/api/recurring", headers=auth(t)).json()
    assert len(lst["items"]) == 1 and lst["totals"]["count"] == 0 and Decimal(str(lst["totals"]["monthly_cost"])) == 0
    assert client.put(f"/api/recurring/{rid}", json={"amount": "-5"}, headers=auth(t)).status_code == 422
    assert client.put(f"/api/recurring/{rid}", json={"status": "ignored"}, headers=auth(t)).status_code == 422


def test_delete_confirmed_then_pattern_is_suggested_again(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    rid = client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(t)).json()["id"]
    assert client.delete(f"/api/recurring/{rid}", headers=auth(t)).status_code == 204
    assert client.get("/api/recurring", headers=auth(t)).json()["items"] == []
    assert by_key(cands(client, t), "netflix") is not None
    assert client.delete(f"/api/recurring/{rid}", headers=auth(t)).status_code == 404


def test_deleting_underlying_transactions_removes_candidate_but_keeps_confirmed_record(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    monthly(db_session, u, "Spotify", 119, date(2026, 9, 15), 6)
    client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(t))
    db_session.query(Transaction).filter(Transaction.user_id == u.id).delete()
    db_session.commit()
    assert cands(client, t) == []  # no history, nothing to detect
    rec = client.get("/api/recurring", headers=auth(t)).json()["items"][0]
    assert rec["merchant"] == "Netflix" and rec["last_date"] == "2026-09-08" and rec["next_expected"] == "2026-10-08"


def test_confirmed_record_tracks_new_payments(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(t))
    add_tx(db_session, u, 649, date(2026, 10, 3), "Netflix")  # paid early this month
    db_session.commit()
    rec = client.get("/api/recurring", headers=auth(t)).json()["items"][0]
    # The subscription renews on the 8th; one early payment does not move the billing day, it just
    # means October's cycle is done, so the next one is November 8.
    assert rec["last_date"] == "2026-10-03" and rec["next_expected"] == "2026-11-08"


def test_manual_recurring_and_duplicates(client, db_session, freeze):
    t, u = setup(client, db_session)
    body = {"merchant": "  House   Rent ", "amount": "12000", "frequency": "monthly", "next_date": "2026-10-31"}
    r = client.post("/api/recurring", json=body, headers=auth(t))
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["merchant"] == "House Rent" and rec["source"] == "manual" and rec["confidence"] is None
    assert rec["last_date"] == "2026-09-30" and rec["next_expected"] == "2026-10-31"
    assert client.post("/api/recurring", json={**body, "merchant": "house rent"}, headers=auth(t)).status_code == 409
    assert client.post("/api/recurring", json={**body, "merchant": "X", "amount": "0"}, headers=auth(t)).status_code == 422
    assert client.post("/api/recurring", json={**body, "merchant": "X", "frequency": "daily"}, headers=auth(t)).status_code == 422


# ---------- subscriptions view ----------

def test_subscriptions_summary_and_sorting(client, db_session, freeze):
    t, u = setup(client, db_session)
    ent, sub = cat(db_session, u, "Entertainment"), cat(db_session, u, "Subscriptions")
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6, category=sub)
    monthly(db_session, u, "Spotify", 119, date(2026, 9, 25), 6, category=sub)
    monthly(db_session, u, "Gym", 1500, date(2026, 9, 5), 6, category=ent)
    for m in ("netflix", "spotify", "gym"):
        client.post("/api/recurring/confirm", json={"merchant_key": m}, headers=auth(t))

    def names(**p):
        r = client.get("/api/subscriptions", params=p, headers=auth(t))
        assert r.status_code == 200, r.text
        return [i["merchant"] for i in r.json()["items"]], r.json()

    assert names(sort="cost")[0] == ["Gym", "Netflix", "Spotify"]
    assert names(sort="monthly")[0] == ["Gym", "Netflix", "Spotify"]
    assert names(sort="renewal")[0] == ["Gym", "Netflix", "Spotify"]  # Oct 5, Oct 8, Oct 25
    assert names(sort="category")[0] == ["Gym", "Netflix", "Spotify"]  # Entertainment < Subscriptions
    assert names(sort="cost", order="asc")[0] == ["Spotify", "Netflix", "Gym"]
    _, body = names()
    assert Decimal(str(body["totals"]["monthly_cost"])) == 2268
    assert Decimal(str(body["totals"]["annual_cost"])) == 27216
    assert client.get("/api/subscriptions", params={"sort": "bogus"}, headers=auth(t)).status_code == 422


def test_subscriptions_counts_pending_review(client, db_session, freeze):
    t, u = setup(client, db_session)
    monthly(db_session, u, "Netflix", 649, date(2026, 9, 8), 6)
    assert client.get("/api/subscriptions", headers=auth(t)).json()["pending_review"] == 1


def test_empty_state(client, db_session, freeze):
    t, _ = setup(client, db_session)
    assert cands(client, t) == []
    body = client.get("/api/subscriptions", headers=auth(t)).json()
    assert body["items"] == [] and body["totals"]["count"] == 0 and Decimal(str(body["totals"]["annual_cost"])) == 0


# ---------- isolation ----------

def test_recurring_isolated_between_users(client, db_session, freeze):
    ta, ua = setup(client, db_session, "a@example.com")
    monthly(db_session, ua, "Netflix", 649, date(2026, 9, 8), 6)
    rid = client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(ta)).json()["id"]
    client.cookies.clear()
    tb, ub = setup(client, db_session, "b@example.com")
    assert client.get("/api/recurring", headers=auth(tb)).json()["items"] == []
    assert cands(client, tb) == []
    assert client.get("/api/subscriptions", headers=auth(tb)).json()["items"] == []
    assert client.put(f"/api/recurring/{rid}", json={"amount": "1"}, headers=auth(tb)).status_code == 404
    assert client.delete(f"/api/recurring/{rid}", headers=auth(tb)).status_code == 404
    assert client.post("/api/recurring/confirm", json={"merchant_key": "netflix"}, headers=auth(tb)).status_code == 404
    # B's categories cannot be attached to A's records and vice versa
    monthly(db_session, ub, "Gym", 1500, date(2026, 9, 5), 6)
    a_cat = cat(db_session, ua, "Entertainment")
    assert client.post("/api/recurring/confirm", json={"merchant_key": "gym", "category_id": a_cat.id},
                       headers=auth(tb)).status_code == 422
    assert client.get("/api/recurring", headers=auth(ta)).json()["items"][0]["merchant"] == "Netflix"
