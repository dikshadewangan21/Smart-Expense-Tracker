"""Net worth = assets - liabilities, computed from stored rows, with a real history.

Account balance on a date D
  * base = the latest valuation on or before D (value counted at the END of its date), else the opening balance
  * balance = base + income - expense - transfers out + transfers in, using transactions dated after the
    valuation date (or all of them, when there is no valuation) and on or before D
  * a transfer only counts when it names BOTH accounts (older rows without a destination are ignored)
  * only transactions in the user's own currency count; others are reported, not converted
Debt on a date D: remaining now + principal paid after D; a debt that began after D isn't counted.

Classification (spec: assets = cash, bank, investments, property, other; liabilities = loans, credit card, other debt)
  assets:      cash/wallet accounts, bank accounts, investment accounts, property accounts, other accounts,
               credit-card accounts that are in credit, and money lent to others
  liabilities: loans (personal/education/borrowed debts), credit cards (card accounts with a negative balance
               and credit-card debts), other debt (any other account with a negative balance)
Goals are NOT counted: they track money that is already inside an account, so adding them would count it twice.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Account, AccountValuation, Debt, DebtPayment, Transaction
from app.services.debts import is_owed
from app.services.periods import add_months, month_end

ZERO = Decimal("0")
CENT = Decimal("0.01")

ASSET_LINES = [("cash", "Cash"), ("bank", "Bank accounts"), ("investments", "Investments"), ("property", "Property"),
               ("lent", "Money lent to others"), ("other_assets", "Other assets")]
LIABILITY_LINES = [("loans", "Loans"), ("credit_card", "Credit cards"), ("other_debt", "Other debt")]
KIND_TO_ASSET = {"cash": "cash", "wallet": "cash", "bank": "bank", "investment": "investments",
                 "property": "property", "other": "other_assets", "credit_card": "other_assets"}


class _Ledger:
    """Everything needed to value the user's accounts and debts on any date, loaded once."""

    def __init__(self, db: Session, user, include_archived: bool = False):
        q = select(Account).where(Account.user_id == user.id)
        if not include_archived:
            q = q.where(Account.archived.is_(False))
        self.accounts = list(db.scalars(q.order_by(Account.id)))
        ids = [a.id for a in self.accounts]
        self.deltas: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        self.vals: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        self.unassigned: list[tuple[date, Decimal, int]] = []  # (date, net effect, number of transactions)
        self.excluded_other_currency = 0
        if ids:
            rows = db.execute(select(Transaction.account_id, Transaction.to_account_id, Transaction.type, Transaction.date,
                                     func.sum(Transaction.amount)).where(
                Transaction.user_id == user.id, Transaction.currency == user.currency,
                (Transaction.account_id.in_(ids)) | (Transaction.to_account_id.in_(ids)))
                .group_by(Transaction.account_id, Transaction.to_account_id, Transaction.type, Transaction.date))
            for acc, to, typ, d, amt in rows:
                amt = Decimal(amt)
                if typ == "income" and acc in ids:
                    self.deltas[acc].append((d, amt))
                elif typ == "expense" and acc in ids:
                    self.deltas[acc].append((d, -amt))
                elif typ == "transfer" and acc is not None and to is not None:
                    if acc in ids:
                        self.deltas[acc].append((d, -amt))
                    if to in ids:
                        self.deltas[to].append((d, amt))
            for acc, d, v in db.execute(select(AccountValuation.account_id, AccountValuation.date, AccountValuation.value)
                                        .where(AccountValuation.account_id.in_(ids)).order_by(AccountValuation.date)):
                self.vals[acc].append((d, Decimal(v)))
        for d, typ, amt, n in db.execute(select(Transaction.date, Transaction.type, func.sum(Transaction.amount), func.count()).where(
                Transaction.user_id == user.id, Transaction.currency == user.currency, Transaction.account_id.is_(None),
                Transaction.type.in_(("income", "expense"))).group_by(Transaction.date, Transaction.type)):
            self.unassigned.append((d, Decimal(amt) if typ == "income" else -Decimal(amt), n))
        self.excluded_other_currency = db.scalar(select(func.count()).where(
            Transaction.user_id == user.id, Transaction.currency != user.currency, Transaction.type != "transfer")) or 0
        self.debts = list(db.scalars(select(Debt).where(Debt.user_id == user.id).order_by(Debt.id)))
        dids = [d.id for d in self.debts]
        self.paid: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        if dids:
            for did, d, p in db.execute(select(DebtPayment.debt_id, DebtPayment.date, DebtPayment.principal_paid)
                                        .where(DebtPayment.debt_id.in_(dids))):
                self.paid[did].append((d, Decimal(p)))

    def balance(self, a: Account, on: date) -> Decimal:
        base, since = Decimal(a.opening_balance), None
        for d, v in self.vals.get(a.id, []):
            if d <= on:
                base, since = v, d
        return base + sum((x for d, x in self.deltas.get(a.id, []) if d <= on and (since is None or d > since)), ZERO)

    def debt_remaining(self, d: Debt, on: date) -> Decimal | None:
        if d.start_date is not None and on < d.start_date:
            return None
        return Decimal(d.remaining) + sum((p for pd, p in self.paid.get(d.id, []) if pd > on), ZERO)

    def valued_on(self, a: Account, on: date) -> date | None:
        ds = [d for d, _ in self.vals.get(a.id, []) if d <= on]
        return max(ds) if ds else None


def _position(led: _Ledger, on: date) -> dict:
    assets = {k: {"amount": ZERO, "items": []} for k, _ in ASSET_LINES}
    liabs = {k: {"amount": ZERO, "items": []} for k, _ in LIABILITY_LINES}

    def put(group, key, name, amt, **extra):
        group[key]["amount"] += amt
        group[key]["items"].append({"name": name, "amount": amt, **extra})

    for a in led.accounts:
        bal = led.balance(a, on)
        if bal >= 0:
            put(assets, KIND_TO_ASSET[a.kind], a.name, bal, account_id=a.id)
        elif a.kind == "credit_card":
            put(liabs, "credit_card", a.name, -bal, account_id=a.id)
        else:
            put(liabs, "other_debt", a.name, -bal, account_id=a.id)
    for d in led.debts:
        rem = led.debt_remaining(d, on)
        if rem is None or rem <= 0:
            continue
        if not is_owed(d):
            put(assets, "lent", d.name, rem, debt_id=d.id)
        elif d.kind == "credit_card":
            put(liabs, "credit_card", d.name, rem, debt_id=d.id)
        else:
            put(liabs, "loans", d.name, rem, debt_id=d.id)
    a_tot = sum((v["amount"] for v in assets.values()), ZERO)
    l_tot = sum((v["amount"] for v in liabs.values()), ZERO)
    return {"assets": a_tot, "liabilities": l_tot, "net_worth": a_tot - l_tot, "_a": assets, "_l": liabs}


def totals(db: Session, user, today: date) -> dict:
    """Assets, liabilities and net worth today: what the dashboard shows."""
    p = _position(_Ledger(db, user), today)
    return {k: p[k] for k in ("assets", "liabilities", "net_worth")}


def month_ends(today: date, months: int) -> list[date]:
    """The last `months` completed month-ends before today."""
    first = today.replace(day=1)
    return [month_end(add_months(first, -k)) for k in range(months, 0, -1)]


def build(db: Session, user, today: date, months: int = 12) -> dict:
    led = _Ledger(db, user)
    cur = _position(led, today)
    trend = []
    for d in month_ends(today, months) + [today]:
        p = _position(led, d)
        trend.append({"date": d, "label": d.strftime("%b %Y") if d != today else "Today",
                      "assets": p["assets"], "liabilities": p["liabilities"], "net_worth": p["net_worth"]})
    prev_date = add_months(today, -1)
    prev = _position(led, prev_date)

    def lines(spec, grp):
        return [{"key": k, "label": lab, "amount": grp[k]["amount"], "items": grp[k]["items"]} for k, lab in spec if grp[k]["items"]]

    unassigned_net = sum((x for d, x, _ in led.unassigned if d <= today), ZERO)
    n_unassigned = sum(n for d, _, n in led.unassigned if d <= today)
    notes = []
    if n_unassigned:
        notes.append("Some transactions are not linked to an account, so they are not part of net worth. "
                     "They do count in your dashboard's total balance.")
    if led.excluded_other_currency:
        notes.append(f"{led.excluded_other_currency} transaction(s) in another currency are not included.")
    return {
        "as_of": today, "currency": user.currency,
        "assets": cur["assets"], "liabilities": cur["liabilities"], "net_worth": cur["net_worth"],
        "assets_breakdown": lines(ASSET_LINES, cur["_a"]), "liabilities_breakdown": lines(LIABILITY_LINES, cur["_l"]),
        "accounts": [{"id": a.id, "name": a.name, "kind": a.kind, "balance": led.balance(a, today),
                      "valued_on": led.valued_on(a, today), "opening_balance": a.opening_balance} for a in led.accounts],
        "trend": trend,
        "change": {"compared_to": prev_date, "net_worth": cur["net_worth"] - prev["net_worth"],
                   "assets": cur["assets"] - prev["assets"], "liabilities": cur["liabilities"] - prev["liabilities"]},
        "unassigned": {"count": n_unassigned, "net": unassigned_net},
        "excluded_other_currency": led.excluded_other_currency, "notes": notes,
    }
