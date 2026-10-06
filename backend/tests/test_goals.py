"""Goals: every expected number below is worked out by hand in the comment next to it.
Clock is frozen at Sun 2026-10-04 (IST)."""
from datetime import date
from decimal import Decimal

import pytest

from app.services.goals import months_left
from tests.conftest import auth, register
from tests.helpers import user_by_email


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def t(client, freeze):
    return register(client, "a@example.com")


def mk(client, t, **over):
    body = {"name": "New Laptop", "kind": "laptop", "target_amount": "80000", "current_amount": "32000", "target_date": "2027-06-04"}
    body.update(over)
    r = client.post("/api/goals", json=body, headers=auth(t))
    assert r.status_code == 201, r.text
    return r.json()


def contribute(client, t, gid, amount, on=None, **kw):
    body = {"amount": str(amount), **({"date": on} if on else {}), **kw}
    return client.post(f"/api/goals/{gid}/contributions", json=body, headers=auth(t))


def test_months_left_rounds_up_and_is_at_least_one():
    today = date(2026, 10, 4)
    assert months_left(today, date(2026, 10, 5)) == 1          # 1 day
    assert months_left(today, date(2026, 11, 3)) == 1          # 30 days = 0.99 month
    assert months_left(today, date(2026, 11, 4)) == 2          # 31 days = 1.02 months
    assert months_left(today, date(2027, 6, 4)) == 8           # 243 days = 7.98 months


def test_spec_example_laptop_needs_6000_a_month(client, t):
    g = mk(client, t)
    # remaining 80000-32000 = 48000; 243 days -> 8 months; 48000/8 = 6000
    assert D(g["remaining"]) == 48000 and g["percent"] == 40.0 and g["status"] == "active"
    assert g["months_left"] == 8 and D(g["required_monthly"]) == D("6000.00")
    assert g["pace_monthly"] is None and g["estimated_completion"] is None and g["on_track"] is None
    assert any("No contributions yet" in n for n in g["notes"])  # says why there is no estimate


def test_required_monthly_rounds_up_to_the_paisa(client, t):
    g = mk(client, t, target_amount="1000", current_amount="0", target_date="2027-06-04")
    assert D(g["required_monthly"]) == D("125.00")                # 1000/8
    g = mk(client, t, target_amount="1000", current_amount="0", target_date="2027-05-04")  # 212 days -> 7 months
    assert g["months_left"] == 7 and D(g["required_monthly"]) == D("142.86")  # 142.857... rounds UP


def test_validation(client, t):
    h = auth(t)
    assert client.post("/api/goals", json={"name": "x", "target_amount": "0"}, headers=h).status_code == 422
    assert client.post("/api/goals", json={"name": "x", "target_amount": "100", "current_amount": "-1"}, headers=h).status_code == 422
    assert client.post("/api/goals", json={"name": "  ", "target_amount": "100"}, headers=h).status_code == 422
    assert client.post("/api/goals", json={"name": "x", "target_amount": "100", "target_date": "2026-10-04"}, headers=h).status_code == 422
    assert client.post("/api/goals", json={"name": "x", "kind": "yacht", "target_amount": "100"}, headers=h).status_code == 422


def test_on_track_and_estimated_completion(client, t):
    g = mk(client, t)
    r = contribute(client, t, g["id"], 6000, "2026-10-01")
    assert r.status_code == 201, r.text
    g = r.json()
    # current 32000+6000 = 38000, remaining 42000. First contribution 3 days ago -> 1-month window -> pace 6000.
    assert D(g["current_amount"]) == 38000 and D(g["remaining"]) == 42000
    assert D(g["pace_monthly"]) == D("6000.00")
    # ceil(42000/6000) = 7 months from 2026-10-04
    assert g["estimated_completion"] == "2027-05-04" and g["on_track"] is True and g["extra_needed_monthly"] is None


def test_finishing_exactly_on_the_target_date_counts_as_on_track(client, t):
    g = mk(client, t, target_amount="7000", current_amount="0", target_date="2027-04-04")
    g = contribute(client, t, g["id"], 1000, "2026-10-01").json()
    # remaining 6000 at 1000/month -> exactly 6 months -> 2027-04-04, which IS the target date
    assert g["estimated_completion"] == "2027-04-04" and g["on_track"] is True


def test_estimate_rounds_the_months_up_never_down(client, t):
    g = mk(client, t, target_amount="7500", current_amount="0", target_date=None)
    g = contribute(client, t, g["id"], 1000, "2026-10-01").json()
    # remaining 6500 at 1000/month = 6.5 -> 7 months, not 6
    assert g["estimated_completion"] == "2027-05-04"


def test_behind_schedule_says_how_much_more(client, t):
    g = mk(client, t)
    g = contribute(client, t, g["id"], 1000, "2026-10-02").json()
    # remaining 47000; pace 1000/month -> 47 months -> 2030-09-04; required 47000/8 = 5875.00
    assert g["estimated_completion"] == "2030-09-04" and g["on_track"] is False
    assert D(g["required_monthly"]) == D("5875.00") and D(g["extra_needed_monthly"]) == D("4875.00")


def test_pace_averages_over_three_months_once_history_is_long_enough(client, t):
    g = mk(client, t)
    contribute(client, t, g["id"], 3000, "2026-07-10")
    g = contribute(client, t, g["id"], 3000, "2026-09-20").json()
    # first contribution 86 days ago -> 3-month window (91 days, from Jul 6) holds both: 6000/3 = 2000
    assert D(g["pace_monthly"]) == D("2000.00")


def test_old_contributions_outside_the_window_give_no_estimate(client, t):
    g = mk(client, t)
    g = contribute(client, t, g["id"], 5000, "2026-05-01").json()
    assert g["pace_monthly"] is None and g["estimated_completion"] is None
    assert any("No net contributions in the last 3 month" in n for n in g["notes"])


def test_withdrawals_reduce_saved_and_cancel_pace(client, t):
    g = mk(client, t, current_amount="0")
    contribute(client, t, g["id"], 5000, "2026-10-01")
    g = contribute(client, t, g["id"], -5000, "2026-10-02").json()
    assert D(g["current_amount"]) == 0 and g["pace_monthly"] is None   # net zero: nothing to project
    r = contribute(client, t, g["id"], -1)
    assert r.status_code == 422 and "more than what is saved" in r.json()["detail"]
    assert contribute(client, t, g["id"], 0).status_code == 422


def test_future_contribution_is_rejected(client, t):
    g = mk(client, t)
    assert contribute(client, t, g["id"], 100, "2026-10-05").status_code == 422


def test_deleting_a_contribution_takes_the_money_back_but_never_below_zero(client, t):
    g = mk(client, t, current_amount="0")
    c1 = contribute(client, t, g["id"], 100, "2026-10-01").json()["contributions"][0]["id"]
    contribute(client, t, g["id"], -100, "2026-10-02")           # saved is now 0
    r = client.delete(f"/api/goals/{g['id']}/contributions/{c1}", headers=auth(t))
    assert r.status_code == 422                                     # would be -100
    withdrawal = client.get(f"/api/goals/{g['id']}", headers=auth(t)).json()["contributions"][0]["id"]
    r = client.delete(f"/api/goals/{g['id']}/contributions/{withdrawal}", headers=auth(t))
    assert r.status_code == 200 and D(r.json()["current_amount"]) == 100
    r = client.delete(f"/api/goals/{g['id']}/contributions/{c1}", headers=auth(t))
    assert r.status_code == 200 and D(r.json()["current_amount"]) == 0 and r.json()["contributions"] == []


def test_completed_and_overdue_states(client, t):
    done = mk(client, t, name="Phone", kind="phone", target_amount="500", current_amount="500")
    assert done["status"] == "completed" and done["required_monthly"] is None and done["percent"] == 100.0
    over = mk(client, t, name="Trip", target_amount="1000", current_amount="100")
    r = client.put(f"/api/goals/{over['id']}", json={"target_date": "2026-09-01"}, headers=auth(t))
    assert r.status_code == 200
    g = r.json()
    assert g["status"] == "overdue" and g["required_monthly"] is None and any("target date has passed" in n for n in g["notes"])
    # contributions beyond the target are allowed and cap the percent at 100
    g = contribute(client, t, done["id"], 50).json()
    assert D(g["current_amount"]) == 550 and g["percent"] == 100.0 and D(g["remaining"]) == 0


def test_put_edits_target_but_cannot_set_the_saved_amount(client, t):
    g = mk(client, t)
    r = client.put(f"/api/goals/{g['id']}", json={"name": "  Gaming   PC ", "target_amount": "90000", "current_amount": "99999"}, headers=auth(t))
    assert r.status_code == 200
    assert r.json()["name"] == "Gaming PC" and D(r.json()["target_amount"]) == 90000 and D(r.json()["current_amount"]) == 32000
    r = client.put(f"/api/goals/{g['id']}", json={"clear_target_date": True}, headers=auth(t))
    assert r.json()["target_date"] is None and r.json()["required_monthly"] is None


def test_list_orders_overdue_then_active_then_completed_and_summarises(client, t):
    done = mk(client, t, name="Done", target_amount="100", current_amount="100", target_date=None)
    soon = mk(client, t, name="Soon", target_amount="1000", current_amount="0", target_date="2026-12-04")
    later = mk(client, t, name="Later", target_amount="3000", current_amount="1000", target_date="2027-06-04")
    late = mk(client, t, name="Late", target_amount="200", current_amount="50")
    client.put(f"/api/goals/{late['id']}", json={"target_date": "2026-01-01"}, headers=auth(t))
    body = client.get("/api/goals", headers=auth(t)).json()
    assert [g["name"] for g in body["items"]] == ["Late", "Soon", "Later", "Done"]
    s = body["summary"]
    # target 100+1000+3000+200 = 4300; saved 100+0+1000+50 = 1150
    assert s["count"] == 4 and s["active"] == 3 and s["completed"] == 1
    assert D(s["total_target"]) == 4300 and D(s["total_saved"]) == 1150 and round(s["percent"], 2) == round(1150 / 4300 * 100, 2)
    # Soon: 61 days -> 3 months -> 333.34; Later: 2000 over 8 months = 250; overdue/completed add nothing
    assert D(s["required_monthly_total"]) == D("333.34") + D("250.00")
    assert done and soon and later


def test_users_cannot_touch_each_others_goals(client, db_session, t):
    g = mk(client, t)
    cid = contribute(client, t, g["id"], 10, "2026-10-01").json()["contributions"][0]["id"]
    client.cookies.clear()
    b = register(client, "b@example.com")
    h = auth(b)
    assert client.get("/api/goals", headers=h).json()["items"] == []
    assert client.get(f"/api/goals/{g['id']}", headers=h).status_code == 404
    assert client.put(f"/api/goals/{g['id']}", json={"name": "x"}, headers=h).status_code == 404
    assert client.delete(f"/api/goals/{g['id']}", headers=h).status_code == 404
    assert contribute(client, b, g["id"], 5).status_code == 404
    assert client.delete(f"/api/goals/{g['id']}/contributions/{cid}", headers=h).status_code == 404
    assert D(client.get(f"/api/goals/{g['id']}", headers=auth(t)).json()["current_amount"]) == 32010   # untouched


def test_delete_goal_removes_its_contributions(client, db_session, t):
    from app.models.core import GoalContribution
    g = mk(client, t)
    contribute(client, t, g["id"], 10, "2026-10-01")
    assert client.delete(f"/api/goals/{g['id']}", headers=auth(t)).status_code == 204
    assert client.get(f"/api/goals/{g['id']}", headers=auth(t)).status_code == 404
    assert db_session.query(GoalContribution).count() == 0


def test_dashboard_goals_carry_the_computed_fields(client, t):
    mk(client, t)
    d = client.get("/api/dashboard", headers=auth(t)).json()
    g = d["goals"][0]
    assert g["name"] == "New Laptop" and D(g["required_monthly"]) == D("6000.00") and g["status"] == "active" and g["percent"] == 40.0


def test_two_emergency_goals_do_not_break_the_health_score_and_are_pooled(client, t):
    mk(client, t, name="EF 1", kind="emergency_fund", target_amount="100000", current_amount="50000")
    mk(client, t, name="EF 2", kind="emergency_fund", target_amount="100000", current_amount="30000")
    r = client.get("/api/dashboard", headers=auth(t))
    assert r.status_code == 200
    ef = next(c for c in r.json()["financial_health"]["components"] if c["key"] == "emergency_fund")
    assert ef["value"] == 40.0                                       # (50000+30000)/(100000+100000)
