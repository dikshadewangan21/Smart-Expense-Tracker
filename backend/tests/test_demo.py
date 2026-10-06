from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.core import Account, Bill, Category, Debt, Goal, RecurringTransaction, Transaction, User
from app.seed import demo
from app.services import recurring as rec_svc
from tests.conftest import auth, register
from tests.helpers import add_tx, cat, user_by_email

TODAY = date(2026, 10, 4)


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def seeded(db_session, freeze):
    info = demo.seed_demo(db_session, TODAY, password="demo-pass-12345")
    return info, demo.get_demo_user(db_session)


def test_history_spans_at_least_six_months_with_all_required_data(db_session, seeded):
    info, u = seeded
    first, last = db_session.execute(select(func.min(Transaction.date), func.max(Transaction.date)).where(Transaction.user_id == u.id)).one()
    assert first == date(2026, 4, 1) and last <= TODAY and info["months"] == 7
    months = {d.strftime("%Y-%m") for (d,) in db_session.execute(select(Transaction.date).where(Transaction.user_id == u.id))}
    assert len(months) == 7
    cats = {n for (n,) in db_session.execute(select(Category.name).join(Transaction, Transaction.category_id == Category.id)
                                             .where(Transaction.user_id == u.id).distinct())}
    for need in ("Food", "Groceries", "Shopping", "Transport", "Rent", "Bills", "Entertainment", "Health", "Education", "Salary", "Freelance", "Subscriptions"):
        assert need in cats, need
    methods = {m for (m,) in db_session.execute(select(Transaction.payment_method).where(Transaction.user_id == u.id).distinct())}
    assert {"upi", "cash", "debit_card", "credit_card", "bank_transfer"} <= methods
    assert db_session.query(Transaction).filter(Transaction.user_id == u.id, Transaction.type == "income").count() >= 9  # 7 salaries + 2 freelance
    assert db_session.query(Account).filter_by(user_id=u.id).count() == 4
    assert db_session.query(Goal).filter_by(user_id=u.id).count() == 3 and db_session.query(Debt).filter_by(user_id=u.id).count() == 2
    assert {b.kind for b in db_session.query(Bill).filter_by(user_id=u.id)} >= {"rent", "electricity", "internet", "phone", "emi", "credit_card", "insurance", "custom"}
    assert all(t.source == "demo" for t in db_session.query(Transaction).filter_by(user_id=u.id))


def test_demo_user_is_flagged_and_everything_belongs_to_it(db_session, seeded):
    _, u = seeded
    assert u.is_demo is True and u.email == demo.DEMO_EMAIL and u.onboarded
    others = db_session.query(Transaction).filter(Transaction.user_id != u.id).count()
    assert others == 0


def test_detection_finds_real_subscriptions_and_ignores_noise(db_session, seeded):
    _, u = seeded
    names = {c.merchant for c in rec_svc.detect(db_session, u, TODAY)}
    assert names == {"Cult.fit", "Namma Metro", "Audible", "Google One"}  # Netflix/Spotify/salary already confirmed
    confirmed = {r.merchant_key for r in db_session.query(RecurringTransaction).filter_by(user_id=u.id, status="confirmed")}
    assert confirmed == {"netflix", "spotify", "acme technologies"}
    noisy = {c.merchant for c in rec_svc.detect(db_session, u, TODAY, include_uncertain=True) if not c.suggested}
    assert noisy and not noisy & names  # random shopping looks 'possible' at best, never suggested


def test_seed_is_deterministic(db_session, freeze):
    a = demo.seed_demo(db_session, TODAY, password="x" * 12)
    u = demo.get_demo_user(db_session)
    first = sorted((t.date, str(t.amount), t.merchant) for t in db_session.query(Transaction).filter_by(user_id=u.id))
    b = demo.reset_demo(db_session, TODAY, password="x" * 12)
    u2 = demo.get_demo_user(db_session)
    second = sorted((t.date, str(t.amount), t.merchant) for t in db_session.query(Transaction).filter_by(user_id=u2.id))
    assert a["transactions"] == b["transactions"] and first == second


def test_dashboard_analytics_bills_and_calendar_work_on_demo_data(client, db_session, seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_demo", True)
    r = client.post("/api/auth/login", json={"email": demo.DEMO_EMAIL, "password": "demo-pass-12345"})
    assert r.status_code == 200
    h = auth(r.json()["access_token"])
    assert client.get("/api/auth/me", headers=h).json()["is_demo"] is True
    d = client.get("/api/dashboard", headers=h).json()
    oct_expenses = db_session.scalar(select(func.sum(Transaction.amount)).where(
        Transaction.user_id == demo.get_demo_user(db_session).id, Transaction.type == "expense", Transaction.date >= date(2026, 10, 1)))
    assert D(d["cards"]["month_income"]) == 62000 and D(d["cards"]["month_expenses"]) == D(oct_expenses) > 0
    assert d["budget_status"] and d["goals"] and d["financial_health"]["score"] is not None
    assert d["upcoming_payments"]["counts"]["overdue"] == 1 and d["what_changed"]["comparable"] is True
    assert d["recurring_summary"]["pending_review"] == 4 and d["recurring_summary"]["subscriptions_count"] == 2
    a = client.get("/api/analytics", params={"period": "last_6_months"}, headers=h).json()
    assert D(a["totals"]["income"]) > 300000 and a["by_merchant"]["top"] and len(a["monthly_trend"]) == 6
    assert D(a["totals"]["savings_rate"]) > 0
    assert any(i["name"] == "Society Maintenance" for i in client.get("/api/upcoming", headers=h).json()["groups"]["overdue"])
    c = client.get("/api/calendar", headers=h).json()
    assert any(e["kind"] == "income" for day in c["days"] for e in day["events"]) and c["summary"]["scheduled"] > 0


def test_demo_cannot_sign_in_unless_enabled(client, db_session, seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_demo", False)
    r = client.post("/api/auth/login", json={"email": demo.DEMO_EMAIL, "password": "demo-pass-12345"})
    assert r.status_code == 403 and "not enabled" in r.json()["detail"]
    wrong = client.post("/api/auth/login", json={"email": demo.DEMO_EMAIL, "password": "wrong-password-1"})
    assert wrong.status_code == 401  # a wrong password does not reveal that the account is a demo one


def test_demo_data_never_reaches_normal_accounts(client, db_session, seeded):
    t = register(client, "real@example.com")
    d = client.get("/api/dashboard", headers=auth(t)).json()
    assert D(d["cards"]["month_income"]) == 0 and d["upcoming_payments"]["items"] == [] and d["goals"] == []
    assert client.get("/api/transactions", headers=auth(t)).json()["total"] == 0
    assert client.get("/api/bills", headers=auth(t)).json()["items"] == []
    assert client.get("/api/recurring/candidates", headers=auth(t)).json() == []
    real = user_by_email(db_session, "real@example.com")
    assert real.is_demo is False
    # registration cannot create or claim the demo account
    dup = client.post("/api/auth/register", json={"email": demo.DEMO_EMAIL, "password": "another-pass-12"})
    assert dup.status_code == 409


def test_reset_and_delete_only_touch_the_demo_user(db_session, freeze):
    from app.models.core import Category
    real = User(email="real@example.com", password_hash="x", name="Real")
    db_session.add(real)
    db_session.flush()
    add_tx(db_session, real, 123, date(2026, 10, 1), "Shop")
    db_session.commit()
    demo.seed_demo(db_session, TODAY, "x" * 12)
    demo.reset_demo(db_session, TODAY, "x" * 12)
    assert db_session.query(Transaction).filter_by(user_id=real.id).count() == 1
    assert demo.delete_demo(db_session) is True and demo.get_demo_user(db_session) is None
    assert db_session.query(Transaction).filter(Transaction.source == "demo").count() == 0
    assert db_session.query(Bill).count() == db_session.query(Goal).count() == db_session.query(Debt).count() == 0  # cascaded
    assert db_session.query(Transaction).filter_by(user_id=real.id).count() == 1
    assert demo.delete_demo(db_session) is False
    assert db_session.get(User, real.id) is not None


def test_refuses_to_touch_a_normal_account_that_holds_the_demo_email(db_session, freeze):
    db_session.add(User(email=demo.DEMO_EMAIL, password_hash="x", name="Squatter", is_demo=False))
    db_session.commit()
    with pytest.raises(demo.DemoSeedError):
        demo.seed_demo(db_session, TODAY)
    with pytest.raises(demo.DemoSeedError):
        demo.delete_demo(db_session)
    with pytest.raises(demo.DemoSeedError):
        demo.reset_demo(db_session, TODAY)
    assert db_session.query(User).filter_by(email=demo.DEMO_EMAIL).count() == 1  # still there, untouched


def test_seeding_twice_without_reset_is_an_error(db_session, seeded):
    with pytest.raises(demo.DemoSeedError):
        demo.seed_demo(db_session, TODAY)


def test_status(db_session, freeze):
    assert demo.status(db_session) == {"exists": False}
    demo.seed_demo(db_session, TODAY, "x" * 12)
    s = demo.status(db_session)
    assert s["exists"] and s["is_demo"] and s["transactions"] > 300 and s["to"] == TODAY


def test_phase4_demo_data_is_internally_consistent(client, db_session, seeded):
    from decimal import Decimal

    from app.models.core import DebtPayment, GoalContribution
    info, u = seeded
    loan = db_session.query(Debt).filter_by(user_id=u.id, name="HDFC Laptop Loan").one()
    pays = db_session.query(DebtPayment).filter_by(debt_id=loan.id).all()
    # the balance is exactly what the payment history implies, and each payment points at a real EMI expense
    assert Decimal(loan.remaining) == Decimal("45000.00")
    assert Decimal(loan.principal) - sum(Decimal(p.principal_paid) for p in pays) == Decimal(loan.remaining)
    assert len(pays) == 6 and all(db_session.get(Transaction, p.transaction_id).merchant == "HDFC Laptop EMI" for p in pays)
    assert loan.bill_id is not None
    # every transfer names two different accounts; none is left half-specified
    transfers = db_session.query(Transaction).filter_by(user_id=u.id, type="transfer").all()
    assert transfers and all(t.account_id and t.to_account_id and t.account_id != t.to_account_id for t in transfers)
    assert db_session.query(GoalContribution).count() == 9


def test_phase4_demo_pages_compute_without_errors(client, db_session, seeded, monkeypatch):
    from app.core.security import create_access_token
    info, u = seeded
    h = {"Authorization": f"Bearer {create_access_token(u.id)}"}
    nw = client.get("/api/net-worth", headers=h).json()
    assert nw["net_worth"] == nw["assets"] - nw["liabilities"] and len(nw["trend"]) == 13
    card = next(a for a in nw["accounts"] if a["kind"] == "credit_card")
    assert -30000 < card["balance"] <= 0                       # the card is paid off monthly, so it never snowballs
    funds = next(a for a in nw["accounts"] if a["kind"] == "investment")
    assert funds["valued_on"] is not None and funds["balance"] > 30000
    goals = {g["name"]: g for g in client.get("/api/goals", headers=h).json()["items"]}
    assert goals["New Laptop"]["on_track"] is True and goals["Emergency Fund"]["on_track"] is False and goals["Goa Trip"]["on_track"] is False
    debts = client.get("/api/debts", headers=h).json()
    assert {d["name"] for d in debts["items"]} == {"HDFC Laptop Loan", "Lent to Ravi"} and debts["summary"]["total_lent"] == 5000
