"""Savings goals. Everything here is arithmetic on stored rows: no prediction beyond a straight-line
extrapolation of the user's own recent contributions, which the API labels as an estimate.

Rules
  * current_amount is the stored truth. Adding a contribution adds to it; deleting one takes it back.
    (Money you set aside is tracked here; it is NOT a transaction and does not count as spending.)
  * required monthly saving = remaining / whole months left (rounded up to the paisa).
    months left = days left / 30.4375, rounded up, at least 1.
  * pace = net contributions over the recent window / months in that window. The window is 1-3 months:
    it never exceeds the time since the first contribution, so one fresh deposit isn't averaged over 3 months.
  * estimated completion = today + ceil(remaining / pace) months. No pace (no, or net-negative, recent
    contributions) means no estimate: we say so instead of guessing.
"""
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Goal, GoalContribution
from app.services.periods import add_months

GOAL_KINDS = ("emergency_fund", "laptop", "travel", "education", "phone", "car", "wedding", "custom")
CENT = Decimal("0.01")
ZERO = Decimal("0")
DAYS_PER_MONTH = Decimal("30.4375")


class GoalError(ValueError):
    """A request the data can't support (maps to HTTP 422)."""


def months_left(today: date, target: date) -> int:
    days = (target - today).days
    return max(1, ceil(Decimal(days) / DAYS_PER_MONTH))


def pace_monthly(db: Session, goal: Goal, today: date) -> tuple[Decimal | None, str | None]:
    """(pace per month, reason it is missing)."""
    rows = list(db.execute(select(GoalContribution.date, GoalContribution.amount).where(GoalContribution.goal_id == goal.id)))
    if not rows:
        return None, "No contributions yet, so there is nothing to project from."
    first = min(r[0] for r in rows)
    window_months = min(max(ceil(Decimal((today - first).days + 1) / DAYS_PER_MONTH), 1), 3)
    window_days = int((window_months * DAYS_PER_MONTH).to_integral_value(ROUND_HALF_UP))
    start = today - timedelta(days=window_days - 1)
    total = sum((Decimal(a) for d, a in rows if start <= d <= today), ZERO)
    if total <= 0:
        return None, f"No net contributions in the last {window_months} month(s), so there is nothing to project from."
    return total / window_months, None


def view(db: Session, goal: Goal, today: date) -> dict:
    target, cur = Decimal(goal.target_amount), Decimal(goal.current_amount)
    remaining = max(target - cur, ZERO)
    out = {
        "id": goal.id, "name": goal.name, "kind": goal.kind, "target_amount": target, "current_amount": cur,
        "remaining": remaining, "percent": float(min(cur / target * 100, Decimal(100))) if target > 0 else None,
        "target_date": goal.target_date, "status": "active", "months_left": None, "required_monthly": None,
        "pace_monthly": None, "estimated_completion": None, "on_track": None, "extra_needed_monthly": None,
        "notes": [],
    }
    if remaining == 0:
        out["status"] = "completed"
        return out
    if goal.target_date is not None:
        if goal.target_date < today:
            out["status"] = "overdue"
            out["notes"].append("The target date has passed. Move it, or keep saving to finish.")
        else:
            m = months_left(today, goal.target_date)
            out["months_left"] = m
            out["required_monthly"] = (remaining / m).quantize(CENT, ROUND_CEILING)
    pace, why = pace_monthly(db, goal, today)
    if pace is None:
        out["notes"].append(why)
        return out
    out["pace_monthly"] = pace.quantize(CENT, ROUND_HALF_UP)
    est = add_months(today, ceil(remaining / pace))
    out["estimated_completion"] = est
    if goal.target_date is not None and out["status"] == "active":
        out["on_track"] = est <= goal.target_date
        if not out["on_track"]:
            out["extra_needed_monthly"] = max(out["required_monthly"] - out["pace_monthly"], ZERO)
    return out


def list_views(db: Session, user_id: int, today: date) -> list[dict]:
    goals = db.scalars(select(Goal).where(Goal.user_id == user_id).order_by(Goal.id))
    views = [view(db, g, today) for g in goals]
    order = {"overdue": 0, "active": 1, "completed": 2}
    far = date.max
    return sorted(views, key=lambda v: (order[v["status"]], v["target_date"] or far, v["id"]))


def summary(views: list[dict]) -> dict:
    active = [v for v in views if v["status"] != "completed"]
    target = sum((v["target_amount"] for v in views), ZERO)
    cur = sum((min(v["current_amount"], v["target_amount"]) for v in views), ZERO)
    return {
        "count": len(views), "active": len(active), "completed": len(views) - len(active),
        "total_target": target, "total_saved": cur,
        "percent": float(cur / target * 100) if target > 0 else None,
        "required_monthly_total": sum((v["required_monthly"] for v in active if v["required_monthly"] is not None), ZERO),
    }


def add_contribution(db: Session, goal: Goal, amount: Decimal, on: date, note: str | None) -> GoalContribution:
    if amount == 0:
        raise GoalError("A contribution can't be zero.")
    new = Decimal(goal.current_amount) + amount
    if new < 0:
        raise GoalError("That withdrawal is more than what is saved in this goal.")
    goal.current_amount = new
    c = GoalContribution(goal_id=goal.id, amount=amount, date=on, note=note)
    db.add(c)
    db.flush()
    return c


def remove_contribution(db: Session, goal: Goal, c: GoalContribution) -> None:
    new = Decimal(goal.current_amount) - Decimal(c.amount)
    if new < 0:
        raise GoalError("Removing this would take the goal below zero. Remove the later withdrawals first.")
    goal.current_amount = new
    db.delete(c)
