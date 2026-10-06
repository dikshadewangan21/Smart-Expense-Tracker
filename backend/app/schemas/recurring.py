from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Frequency = Literal["weekly", "biweekly", "monthly", "quarterly", "yearly"]
FlowType = Literal["expense", "income"]
Amt = Field(gt=0, max_digits=12, decimal_places=2)


def _clean_name(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


class ConfirmIn(BaseModel):
    merchant_key: str = Field(min_length=1, max_length=160)
    type: FlowType = "expense"
    # Optional corrections applied at confirmation time
    frequency: Frequency | None = None
    category_id: int | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    merchant: str | None = Field(default=None, max_length=160)

    _n = field_validator("merchant")(_clean_name)


class IgnoreIn(BaseModel):
    merchant_key: str = Field(min_length=1, max_length=160)
    type: FlowType = "expense"


class RecurringIn(BaseModel):
    type: FlowType = "expense"
    merchant: str = Field(min_length=1, max_length=160)
    amount: Decimal = Amt
    frequency: Frequency
    next_date: date  # the next payment date; the previous occurrence is derived from it
    category_id: int | None = None
    reminder: bool = True

    _n = field_validator("merchant")(_clean_name)


class RecurringUpdate(BaseModel):
    merchant: str | None = Field(default=None, min_length=1, max_length=160)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    frequency: Frequency | None = None
    category_id: int | None = None  # send null explicitly to clear
    reminder: bool | None = None
    status: Literal["confirmed", "paused"] | None = None

    _n = field_validator("merchant")(_clean_name)


class RecurringOut(BaseModel):
    id: int
    type: str
    merchant: str
    merchant_key: str
    amount: Decimal
    frequency: str
    category_id: int | None
    category: str | None
    status: str
    reminder: bool
    last_date: date | None
    next_expected: date | None
    days_until_next: int | None
    monthly_equivalent: Decimal
    annual_cost: Decimal
    confidence: float | None
    occurrences: int
    source: str


class CandidateOut(BaseModel):
    type: str
    merchant_key: str
    merchant: str
    amount: Decimal
    frequency: str
    category_id: int | None
    category: str | None
    last_date: date
    next_expected: date
    occurrences: int
    confidence: float
    suggested: bool
    amount_varies: bool
    monthly_equivalent: Decimal
    annual_cost: Decimal
    reasons: list[str]


class Totals(BaseModel):
    count: int
    monthly_cost: Decimal
    annual_cost: Decimal


class RecurringList(BaseModel):
    items: list[RecurringOut]
    totals: Totals
