from datetime import date
from decimal import Decimal

from app.models.core import (Account, Bill, Budget, BudgetCategory, Category, Debt, Goal, Transaction, User)
from tests.conftest import auth, register

TODAY = date(2026, 10, 15)


def _user(db, email="a@example.com"):
    from sqlalchemy import select
    return db.scalar(select(User).where(User.email == email))


def _cat(db, user, name):
    from sqlalchemy import select
    return db.scalar(select(Category).where(Category.user_id == user.id, Category.name == name))


def _tx(db, user, type_, amount, d, cat=None, account=None):
    db.add(Transaction(user_id=user.id, type=type_, amount=Decimal(amount), date=d,
                       category_id=cat.id if cat else None, account_id=account.id if account else None))


def test_empty_user_gets_none_not_fake_numbers(client):
    token = register(client)
    r = client.get("/api/dashboard", params={"as_of": TODAY.isoformat()}, headers=auth(token))
    assert r.status_code == 200
    d = r.json()
    assert d["cards"]["total_balance"] in (0, "0", "0.0", 0.0)
    assert d["cards"]["budget_remaining"] is None
    assert d["financial_health"]["score"] is None
    assert d["spending_by_category"] == [] and d["goals"] == [] and d["insights"] == []


def test_dashboard_math(client, db_session):
    token = register(client)
    u = _user(db_session)
    bank = Account(user_id=u.id, name="Bank", kind="bank", opening_balance=Decimal("10000"))
    food, rent = _cat(db_session, u, "Food"), _cat(db_session, u, "Rent")
    db_session.add(bank)
    db_session.flush()

    _tx(db_session, u, "income", "50000", date(2026, 10, 1), account=bank)
    _tx(db_session, u, "expense", "8000", date(2026, 10, 2), food, bank)
    _tx(db_session, u, "expense", "12000", date(2026, 10, 3), rent, bank)
    _tx(db_session, u, "expense", "5000", date(2026, 9, 10), food, bank)   # previous month
    _tx(db_session, u, "income", "40000", date(2026, 9, 1), account=bank)  # previous month
    _tx(db_session, u, "transfer", "99999", date(2026, 10, 4), account=bank)  # must be ignored

    b = Budget(user_id=u.id, month=date(2026, 10, 1), total_limit=Decimal("25000"))
    db_session.add(b)
    db_session.flush()
    db_session.add_all([BudgetCategory(budget_id=b.id, category_id=food.id, limit_amount=Decimal("7000")),
                        BudgetCategory(budget_id=b.id, category_id=rent.id, limit_amount=Decimal("12000"))])
    db_session.add(Bill(user_id=u.id, name="Internet", amount=Decimal("999"), due_date=date(2026, 10, 18)))
    db_session.add(Goal(user_id=u.id, name="Laptop", kind="custom", target_amount=Decimal("80000"),
                        current_amount=Decimal("32000")))
    db_session.add(Debt(user_id=u.id, name="Loan", kind="personal", principal=Decimal("100000"),
                        remaining=Decimal("60000"), emi=Decimal("5000")))
    db_session.commit()

    d = client.get("/api/dashboard", params={"as_of": TODAY.isoformat()}, headers=auth(token)).json()
    c = d["cards"]
    # balance = 10000 opening + 90000 income - 25000 expenses = 75000 (the transfer is ignored)
    assert Decimal(str(c["total_balance"])) == Decimal("75000")
    assert Decimal(str(c["month_income"])) == Decimal("50000")
    assert Decimal(str(c["month_expenses"])) == Decimal("20000")
    assert Decimal(str(c["savings"])) == Decimal("30000")
    assert Decimal(str(c["budget_remaining"])) == Decimal("5000")  # 25000 - 20000
    # net worth = bank balance 75000 - debt 60000
    assert Decimal(str(c["net_worth"])) == Decimal("15000")

    cats = {x["category"]: Decimal(str(x["amount"])) for x in d["spending_by_category"]}
    assert cats == {"Food": Decimal("8000"), "Rent": Decimal("12000")}

    lines = {x["category"]: x for x in d["budget_status"]["categories"]}
    assert Decimal(str(lines["Food"]["remaining"])) == Decimal("-1000")
    assert round(lines["Food"]["percent_used"], 1) == 114.3

    up = d["upcoming_payments"]["items"][0]  # Phase 3: grouped upcoming payments (bills + confirmed recurring)
    assert up["name"] == "Internet" and up["days_until"] == 3 and up["group"] == "this_week"
    assert d["goals"][0]["percent"] == 40.0 and Decimal(str(d["goals"][0]["remaining"])) == Decimal("48000")

    trend = {m["month"]: m for m in d["monthly_trend"]}
    assert Decimal(str(trend["2026-09"]["expenses"])) == Decimal("5000")

    # Insight is derived from data: food 8000 vs 5000 last month = +60%
    assert any("60% more on Food" in s for s in d["insights"])


def test_health_score_is_explained_and_bounded(client, db_session):
    token = register(client)
    u = _user(db_session)
    food = _cat(db_session, u, "Food")
    _tx(db_session, u, "income", "50000", date(2026, 10, 1))
    _tx(db_session, u, "expense", "40000", date(2026, 10, 2), food)  # 20% savings rate -> full 30 pts
    db_session.commit()
    h = client.get("/api/dashboard", params={"as_of": TODAY.isoformat()}, headers=auth(token)).json()["financial_health"]
    sr = next(c for c in h["components"] if c["key"] == "savings_rate")
    assert sr["points"] == 30 and sr["value"] == 20.0 and "20%" in sr["reason"]
    assert 0 <= h["score"] <= 100


def test_users_cannot_see_each_others_data(client, db_session):
    token_a = register(client, "a@example.com")
    ua = _user(db_session, "a@example.com")
    _tx(db_session, ua, "income", "77777", date(2026, 10, 1))
    db_session.commit()

    client.cookies.clear()
    token_b = register(client, "b@example.com")
    d = client.get("/api/dashboard", params={"as_of": TODAY.isoformat()}, headers=auth(token_b)).json()
    assert Decimal(str(d["cards"]["month_income"])) == 0
    assert "77777" not in str(d)

    d_a = client.get("/api/dashboard", params={"as_of": TODAY.isoformat()}, headers=auth(token_a)).json()
    assert Decimal(str(d_a["cards"]["month_income"])) == Decimal("77777")
