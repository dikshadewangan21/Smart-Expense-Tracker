from datetime import date
from decimal import Decimal

from tests.conftest import auth, register
from tests.helpers import add_tx, cat, user_by_email


def test_defaults_for_new_users(client):
    t = register(client)
    me = client.get("/api/auth/me", headers=auth(t)).json()
    assert me["timezone"] == "Asia/Kolkata" and me["currency"] == "INR" and me["is_demo"] is False


def test_update_name_and_timezone(client, db_session):
    t = register(client)
    r = client.patch("/api/auth/me", json={"name": "  Asha   K ", "timezone": "America/New_York"}, headers=auth(t))
    assert r.status_code == 200
    assert r.json()["name"] == "Asha K" and r.json()["timezone"] == "America/New_York"
    assert client.get("/api/auth/me", headers=auth(t)).json()["timezone"] == "America/New_York"  # persisted
    only_name = client.patch("/api/auth/me", json={"name": "Asha"}, headers=auth(t)).json()
    assert only_name["name"] == "Asha" and only_name["timezone"] == "America/New_York"  # untouched fields stay
    assert client.patch("/api/auth/me", json={}, headers=auth(t)).status_code == 200


def test_invalid_values_rejected(client):
    t = register(client)
    for bad in ({"timezone": "Mars/Olympus"}, {"timezone": ""}, {"timezone": "../../etc/passwd"}, {"name": "x" * 121}, {"timezone": "x" * 65}):
        assert client.patch("/api/auth/me", json=bad, headers=auth(t)).status_code == 422, bad
    assert client.get("/api/auth/me", headers=auth(t)).json()["timezone"] == "Asia/Kolkata"


def test_requires_auth_and_cannot_change_email_or_flags(client, db_session):
    assert client.patch("/api/auth/me", json={"name": "x"}).status_code == 401
    t = register(client)
    client.patch("/api/auth/me", json={"name": "Z", "email": "evil@example.com", "is_demo": True, "currency": "USD"}, headers=auth(t))
    me = client.get("/api/auth/me", headers=auth(t)).json()
    assert me["email"] == "a@example.com" and me["is_demo"] is False and me["currency"] == "INR"


def test_changing_timezone_changes_todays_period_everywhere(client, db_session, freeze):
    freeze("2026-09-30T19:00:00+00:00")  # 1 Oct in India, 30 Sep in UTC
    t = register(client)
    u = user_by_email(db_session)
    add_tx(db_session, u, 100, date(2026, 9, 30), "Old", category=cat(db_session, u, "Food"))
    add_tx(db_session, u, 200, date(2026, 10, 1), "New", category=cat(db_session, u, "Food"))
    db_session.commit()
    assert client.get("/api/analytics", headers=auth(t)).json()["period"]["start"] == "2026-10-01"
    assert client.get("/api/dashboard", headers=auth(t)).json()["as_of"] == "2026-10-01"
    client.patch("/api/auth/me", json={"timezone": "UTC"}, headers=auth(t))
    a = client.get("/api/analytics", headers=auth(t)).json()
    assert a["period"]["start"] == "2026-09-01" and Decimal(str(a["totals"]["expenses"])) == 100
    assert client.get("/api/dashboard", headers=auth(t)).json()["as_of"] == "2026-09-30"
    assert client.get("/api/calendar", headers=auth(t)).json()["month"] == "2026-09"
