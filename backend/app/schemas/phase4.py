"""Request bodies for goals, debts, accounts and valuations. Responses are plain dicts built by the services."""
import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

GoalKind = Literal["emergency_fund", "laptop", "travel", "education", "phone", "car", "wedding", "custom"]
DebtKind = Literal["personal", "education", "credit_card", "borrowed", "lent"]
AccountKind = Literal["cash", "bank", "wallet", "credit_card", "investment", "property", "other"]
PaymentMethod = Literal["upi", "cash", "debit_card", "credit_card", "bank_transfer", "wallet", "net_banking", "other"]
Money = dict(max_digits=12, decimal_places=2)


def _name(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("Name can't be blank.")
    return v


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: GoalKind = "custom"
    target_amount: Decimal = Field(gt=0, **Money)
    current_amount: Decimal = Field(default=Decimal("0"), ge=0, **Money)  # what is already saved
    target_date: dt.date | None = None
    _n = field_validator("name")(_name)


class GoalUpdate(BaseModel):
    """Saved amount is changed with contributions, not here, so the history always explains the number."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: GoalKind | None = None
    target_amount: Decimal | None = Field(default=None, gt=0, **Money)
    target_date: dt.date | None = None
    clear_target_date: bool = False

    @field_validator("name")
    @classmethod
    def _clean(cls, v):
        return _name(v) if v is not None else None


class ContributionIn(BaseModel):
    amount: Decimal = Field(**Money)  # negative = withdrawal
    date: dt.date | None = None
    note: str | None = Field(default=None, max_length=200)

    @field_validator("amount")
    @classmethod
    def nonzero(cls, v):
        if v == 0:
            raise ValueError("A contribution can't be zero.")
        return v

    @field_validator("note")
    @classmethod
    def _note(cls, v):
        return (" ".join(v.split()) or None) if v is not None else None


class DebtBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: DebtKind
    principal: Decimal = Field(gt=0, **Money)
    interest_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=6, decimal_places=3)
    emi: Decimal | None = Field(default=None, gt=0, **Money)
    due_day: int | None = Field(default=None, ge=1, le=31)
    start_date: dt.date | None = None
    bill_id: int | None = None
    _n = field_validator("name")(_name)


class DebtCreate(DebtBase):
    remaining: Decimal | None = Field(default=None, ge=0, **Money)  # defaults to the principal


class DebtUpdate(DebtBase):
    remaining: Decimal = Field(ge=0, **Money)


class DebtPaymentIn(BaseModel):
    amount: Decimal = Field(gt=0, **Money)
    paid_on: dt.date | None = None
    principal_paid: Decimal | None = Field(default=None, ge=0, **Money)  # default: amount minus one month's interest
    create_transaction: bool | None = None  # default: true for debts you owe, false for money you lent
    account_id: int | None = None
    payment_method: PaymentMethod = "other"


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: AccountKind | None = None
    opening_balance: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    archived: bool | None = None

    @field_validator("name")
    @classmethod
    def _clean(cls, v):
        return _name(v) if v is not None else None


class ValuationIn(BaseModel):
    date: dt.date
    value: Decimal = Field(max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=200)
