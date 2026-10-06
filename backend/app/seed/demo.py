"""Demo data for presentations and testing.

    python -m app.seed.demo seed     create the demo user with ~7 months of realistic data
    python -m app.seed.demo reset    delete the demo user (and all its data) and seed again
    python -m app.seed.demo delete   remove the demo user and all its data
    python -m app.seed.demo status   show whether demo data exists

Isolation guarantees:
  * everything lives under ONE reserved account (DEMO_EMAIL) flagged is_demo=True
  * the commands never modify any other user; if DEMO_EMAIL is held by a normal account they refuse
  * normal registrations never receive demo data
  * the demo account can only sign in when the server runs with ENABLE_DEMO=true
Data is deterministic for a given day (fixed random seed) and always ends "today", so the
dashboard, bills and calendar look current whenever it is seeded.
"""
import argparse
import os
import random
import secrets
import sys
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.security import hash_password
from app.models.core import (Account, AccountValuation, AuditLog, DebtPayment, GoalContribution, Bill, Budget, BudgetCategory, Category, Debt, Goal,
                             RecurringTransaction, Transaction, User)
from app.services import recurring as recurring_svc
from app.services.categories import seed_default_categories
from app.services.periods import add_months, month_end

DEMO_EMAIL = "demo@example.com"
DEMO_NAME = "Demo User (sample data)"
RNG_SEED = 20261004
MONTHS_BACK = 6  # the current month plus six full months before it


class DemoSeedError(Exception):
    pass


def _clamp(y: int, m: int, d: int) -> date:
    return date(y, m, min(d, monthrange(y, m)[1]))


def _next_on_day(today: date, day: int) -> date:
    """The next date with this day-of-month that is strictly after today."""
    this = _clamp(today.year, today.month, day)
    if this > today:
        return this
    n = add_months(today.replace(day=1), 1)
    return _clamp(n.year, n.month, day)


def get_demo_user(db: Session) -> User | None:
    return db.scalar(select(User).where(User.email == DEMO_EMAIL))


def delete_demo(db: Session) -> bool:
    user = get_demo_user(db)
    if user is None:
        return False
    if not user.is_demo:
        raise DemoSeedError(f"{DEMO_EMAIL} belongs to a normal account. Refusing to delete it.")
    db.query(AuditLog).filter(AuditLog.user_id == user.id).delete()
    db.delete(user)  # every child table cascades from users
    db.commit()
    return True


def reset_demo(db: Session, today: date | None = None, password: str | None = None) -> dict:
    delete_demo(db)
    return seed_demo(db, today, password)


def status(db: Session) -> dict:
    user = get_demo_user(db)
    if user is None:
        return {"exists": False}
    if not user.is_demo:
        return {"exists": True, "is_demo": False, "warning": f"{DEMO_EMAIL} is a normal account"}
    n = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id))
    first, last = db.execute(select(func.min(Transaction.date), func.max(Transaction.date)).where(Transaction.user_id == user.id)).one()
    return {"exists": True, "is_demo": True, "email": DEMO_EMAIL, "transactions": n, "from": first, "to": last}


def seed_demo(db: Session, today: date | None = None, password: str | None = None) -> dict:
    existing = get_demo_user(db)
    if existing is not None:
        raise DemoSeedError(
            "Demo data already exists. Run 'reset' to rebuild it." if existing.is_demo
            else f"{DEMO_EMAIL} belongs to a normal account. Refusing to touch it.")
    password = password or secrets.token_urlsafe(12)
    rng = random.Random(RNG_SEED)

    user = User(email=DEMO_EMAIL, password_hash=hash_password(password), name=DEMO_NAME, currency="INR",
                timezone="Asia/Kolkata", monthly_income=Decimal("62000"), income_frequency="monthly",
                monthly_savings_target=Decimal("15000"), budgeting_style="balanced", onboarded=True, is_demo=True)
    db.add(user)
    db.flush()
    today = today or user_today(user)
    seed_default_categories(db, user.id)
    db.flush()
    cats = {c.name: c.id for c in db.scalars(select(Category).where(Category.user_id == user.id, Category.kind == "expense"))}
    inc_cats = {c.name: c.id for c in db.scalars(select(Category).where(Category.user_id == user.id, Category.kind == "income"))}

    hdfc = Account(user_id=user.id, name="HDFC Savings", kind="bank", opening_balance=Decimal("85000"))
    cash = Account(user_id=user.id, name="Cash wallet", kind="cash", opening_balance=Decimal("3000"))
    card = Account(user_id=user.id, name="ICICI Credit Card", kind="credit_card", opening_balance=Decimal("0"))
    funds = Account(user_id=user.id, name="Mutual Funds (SIP)", kind="investment", opening_balance=Decimal("0"))
    db.add_all([hdfc, cash, card, funds])
    db.flush()
    acct = {"upi": hdfc.id, "bank_transfer": hdfc.id, "debit_card": hdfc.id, "net_banking": hdfc.id,
            "cash": cash.id, "credit_card": card.id}

    first_month = add_months(today.replace(day=1), -MONTHS_BACK)
    current_month = today.replace(day=1)
    txs: list[Transaction] = []

    def add(d: date, amount, merchant: str, category: str, pm: str, kind: str = "expense"):
        if d > today:
            return
        txs.append(Transaction(
            user_id=user.id, type=kind, amount=Decimal(str(amount)), currency="INR", date=d, merchant=merchant,
            category_id=(inc_cats if kind == "income" else cats)[category], payment_method=pm,
            account_id=acct[pm], source="demo"))

    # ----- monthly, fixed-date items -----
    months = [add_months(first_month, i) for i in range(MONTHS_BACK + 1)]
    for idx, m in enumerate(months):
        def on(day):
            return _clamp(m.year, m.month, day)
        add(on(1), 62000, "Acme Technologies", "Salary", "bank_transfer", "income")
        if idx in (1, 4):
            add(on(17), rng.randint(8000, 18000), "Freelance - Design client", "Freelance", "upi", "income")
        add(on(2), 500, "Namma Metro", "Transport", "upi")
        add(on(3), 1500, "Cult.fit", "Health", "upi")
        add(on(5), 12000, "Rent", "Rent", "bank_transfer")
        add(on(8), 649, "Netflix", "Subscriptions", "credit_card")
        if m != current_month:  # this month's electricity bill has not been paid yet
            add(on(10), rng.randint(1500, 2100), "BESCOM Electricity", "Bills", "upi")
        add(on(12), 999, "Airtel Broadband", "Bills", "upi")
        add(on(14), 299, "Jio Mobile", "Bills", "upi")
        add(on(15), 119, "Spotify", "Subscriptions", "credit_card")
        add(on(20), 5000, "HDFC Laptop EMI", "EMI & Loans", "bank_transfer")
        add(on(22), 199, "Audible", "Subscriptions", "credit_card")
        add(on(27), 130, "Google One", "Subscriptions", "credit_card")
        if idx == 2:
            add(on(12), 449, "Udemy", "Education", "credit_card")
        if idx == 5:
            add(on(12), 3000, "Coursera", "Education", "credit_card")
        if idx == 3:
            add(on(18), 2400, "IRCTC", "Travel", "net_banking")
            add(on(19), 6000, "Goibibo Hotels", "Travel", "credit_card")

    # ----- day-by-day everyday spending -----
    d = first_month
    while d <= today:
        weekend = d.weekday() >= 5
        boost = 1.25 if d >= current_month else 1.0  # food runs a bit higher this month: a story for What Changed
        if rng.random() < (0.55 if weekend else 0.36) * boost:
            add(d, rng.randint(180, 650), rng.choice(["Swiggy", "Swiggy", "Zomato"]), "Food", rng.choice(["upi", "upi", "credit_card"]))
        if rng.random() < 0.10:
            add(d, rng.randint(120, 480), rng.choice(["Starbucks", "Local Cafe"]), "Food", rng.choice(["credit_card", "cash"]))
        if rng.random() < 0.20:
            add(d, rng.randint(20, 60), "Tea stall", "Food", "cash")
        if rng.random() < 0.11:
            add(d, rng.randint(400, 3200), rng.choice(["BigBasket", "DMart", "Reliance Smart", "Blinkit"]), "Groceries", rng.choice(["upi", "debit_card"]))
        if rng.random() < 0.28:
            add(d, rng.randint(90, 420), rng.choice(["Uber", "Ola", "Rapido"]), "Transport", "upi")
        if rng.random() < 0.18:
            add(d, rng.randint(40, 150), "Auto rickshaw", "Transport", "cash")
        if rng.random() < 0.05:
            add(d, rng.randint(1000, 1800), "Indian Oil", "Transport", "debit_card")
        if rng.random() < 0.07:
            add(d, rng.randint(400, 3500), rng.choice(["Amazon", "Flipkart", "Myntra"]), "Shopping", "credit_card")
        if rng.random() < 0.04:
            add(d, rng.randint(400, 900), "BookMyShow", "Entertainment", "upi")
        if rng.random() < 0.05:
            add(d, rng.randint(200, 1100), "Apollo Pharmacy", "Health", "upi")
        d += timedelta(days=1)
    add(today - timedelta(days=1) if today.day > 1 else today, 8500, "Amazon", "Shopping", "credit_card")  # one large purchase

    # ----- transfers: the card bill is paid from the bank on the 25th, and a SIP goes to the funds on the 7th -----
    card_spend: dict[tuple[int, int], Decimal] = {}
    for t_ in txs:
        if t_.type == "expense" and t_.payment_method == "credit_card":
            k_ = (t_.date.year, t_.date.month)
            card_spend[k_] = card_spend.get(k_, Decimal(0)) + Decimal(t_.amount)
    for idx, m in enumerate(months):
        sip_day = _clamp(m.year, m.month, 7)
        if sip_day <= today:
            txs.append(Transaction(user_id=user.id, type="transfer", amount=Decimal("5000"), currency="INR", date=sip_day,
                                   merchant=None, payment_method="bank_transfer", account_id=hdfc.id, to_account_id=funds.id,
                                   source="demo", notes="Monthly SIP"))
        prev = months[idx - 1] if idx else None
        pay_day = _clamp(m.year, m.month, 25)
        spend = card_spend.get((prev.year, prev.month)) if prev else None
        if spend and pay_day <= today:
            txs.append(Transaction(user_id=user.id, type="transfer", amount=spend, currency="INR", date=pay_day,
                                   merchant=None, payment_method="bank_transfer", account_id=hdfc.id, to_account_id=card.id,
                                   source="demo", notes="Credit card bill payment"))
    # Month-end values of the funds: the SIPs so far, grown by about 1.2% a month (illustrative demo numbers)
    for j, m in enumerate(months):
        end = month_end(m)
        if end < today:
            db.add(AccountValuation(account_id=funds.id, date=end, value=(Decimal(5000 * (j + 1)) * (1 + Decimal("0.012") * (j + 1))).quantize(Decimal("0.01")),
                                    note="Statement value"))

    db.add_all(txs)
    db.flush()

    # ----- budgets (this month and last) -----
    limits = {"Food": 8000, "Groceries": 6000, "Transport": 4000, "Shopping": 5000, "Entertainment": 1500,
              "Subscriptions": 3000, "Health": 5000, "Education": 3000}
    for m in (add_months(current_month, -1), current_month):
        b = Budget(user_id=user.id, month=m, name="Monthly budget", total_limit=Decimal("52000"))
        db.add(b)
        db.flush()
        for name, lim in limits.items():
            db.add(BudgetCategory(budget_id=b.id, category_id=cats[name], limit_amount=Decimal(lim)))

    # ----- bills -----
    def bill(name, kind, amount, due, freq="monthly", category=None, notes=None):
        b_ = Bill(user_id=user.id, name=name, kind=kind, amount=Decimal(str(amount)), due_date=due, frequency=freq,
                  anchor_day=due.day if freq in ("monthly", "quarterly", "yearly") else None,
                  category_id=cats.get(category), auto_repeat=freq != "once", notes=notes)
        db.add(b_)
        db.flush()
        return b_

    bill("Society Maintenance", "custom", 2500, today - timedelta(days=4), notes="Not paid yet: shows an overdue bill")
    bill("Rent", "rent", 12000, _next_on_day(today, 5), category="Rent", notes="Landlord: R. Sharma")
    bill("BESCOM Electricity", "electricity", 1850, _clamp(today.year, today.month, 10), category="Bills",
         notes="Amount varies month to month")
    bill("Airtel Broadband", "internet", 999, _next_on_day(today, 12), category="Bills")
    bill("Jio Mobile", "phone", 299, _next_on_day(today, 14), category="Bills")
    emi_bill = bill("HDFC Laptop EMI", "emi", 5000, _next_on_day(today, 20), category="EMI & Loans")
    bill("ICICI Credit Card", "credit_card", 12000, _next_on_day(today, 25),
         notes="Paying this bill is not recorded as an expense by default: card purchases are already tracked.")
    bill("LIC Insurance", "insurance", 18000, today + timedelta(days=65), "yearly", category="Health")
    bill("Passport renewal", "custom", 1500, today + timedelta(days=9), "once")

    # ----- goals and debt -----
    goal_rows = [
        # name, kind, target, saved now, months to target, monthly contribution over the last three months
        ("Emergency Fund", "emergency_fund", 150000, 62000, 12, 5000),   # behind: 88,000 at 5,000/month > 12 months
        ("New Laptop", "laptop", 80000, 32000, 8, 6500),                 # on track: 48,000 at 6,500/month = 8 months
        ("Goa Trip", "travel", 40000, 12000, 6, 2000),                   # behind: 28,000 at 2,000/month > 6 months
    ]
    for name, kind, target, saved, months_to_go, monthly_in in goal_rows:
        g_ = Goal(user_id=user.id, name=name, kind=kind, target_amount=Decimal(target), current_amount=Decimal(saved),
                  target_date=add_months(today, months_to_go))
        db.add(g_)
        db.flush()
        for days_ago in (70, 40, 10):  # the saved amount already includes these; the rest was there at the start
            db.add(GoalContribution(goal_id=g_.id, amount=Decimal(monthly_in), date=today - timedelta(days=days_ago), note="Monthly saving"))

    # The loan: work the balance backwards from today's 45,000 through the EMI payments already in the history,
    # splitting each at 11.5% a year, so principal, interest paid and the remaining balance all agree.
    emi_txs = sorted((t_ for t_ in txs if t_.merchant == "HDFC Laptop EMI"), key=lambda t_: t_.date)
    rate_m = Decimal("11.5") / 1200
    remaining_after = [Decimal("45000.00")]
    for _ in emi_txs:
        remaining_after.insert(0, ((remaining_after[0] + Decimal(5000)) / (1 + rate_m)).quantize(Decimal("0.01")))
    loan = Debt(user_id=user.id, name="HDFC Laptop Loan", kind="personal", principal=remaining_after[0],
                remaining=remaining_after[-1], interest_rate=Decimal("11.5"), emi=Decimal("5000"), due_day=20,
                start_date=(emi_txs[0].date - timedelta(days=30)) if emi_txs else None, bill_id=emi_bill.id)
    db.add(loan)
    db.flush()
    for k_, t_ in enumerate(emi_txs):
        db.add(DebtPayment(debt_id=loan.id, amount=Decimal(5000), principal_paid=remaining_after[k_] - remaining_after[k_ + 1],
                           date=t_.date, transaction_id=t_.id))
    ravi = Debt(user_id=user.id, name="Lent to Ravi", kind="lent", principal=Decimal("8000"), remaining=Decimal("5000"),
                start_date=add_months(today, -3))
    db.add(ravi)
    db.flush()
    db.add(DebtPayment(debt_id=ravi.id, amount=Decimal("3000"), principal_paid=Decimal("3000"), date=today - timedelta(days=20)))
    db.flush()

    # ----- confirm a few recurring patterns using the real detector; leave the rest for review -----
    confirmed = []
    for key, kind in (("netflix", "expense"), ("spotify", "expense"), ("acme technologies", "income")):
        cand = next((c for c in recurring_svc.detect(db, user, today, kind) if c.merchant_key == key), None)
        if cand is None:
            raise DemoSeedError(f"Self-check failed: the detector did not find '{key}' in the generated data.")
        db.add(recurring_svc.record_from_candidate(user.id, cand, "confirmed"))
        confirmed.append(key)

    db.commit()
    return {"email": DEMO_EMAIL, "password": password, "transactions": len(txs), "from": first_month, "to": today,
            "months": MONTHS_BACK + 1, "confirmed_recurring": confirmed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.seed.demo", description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["seed", "reset", "delete", "status"])
    ap.add_argument("--password", help="demo password (default: $DEMO_PASSWORD, else a random one that is printed once)")
    args = ap.parse_args(argv)
    from app.db.session import SessionLocal  # imported late so --help works without a database

    with SessionLocal() as db:
        try:
            if args.command == "status":
                print(status(db))
            elif args.command == "delete":
                print("Demo user and its data deleted." if delete_demo(db) else "No demo data to delete.")
            else:
                fn = seed_demo if args.command == "seed" else reset_demo
                r = fn(db, password=args.password or os.environ.get("DEMO_PASSWORD"))
                print(f"Demo data ready: {r['transactions']} transactions from {r['from']} to {r['to']}.")
                print(f"  Email:    {r['email']}\n  Password: {r['password']}")
                print("  The demo account can only sign in when the server runs with ENABLE_DEMO=true.")
        except DemoSeedError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
