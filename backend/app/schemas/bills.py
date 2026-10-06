from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.transactions import PaymentMethod

BillKind = Literal["rent", "electricity", "internet", "phone", "insurance", "emi", "credit_card", "custom"]
BillFrequency = Literal["once", "weekly", "monthly", "quarterly", "yearly"]


class BillIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: BillKind = "custom"
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    due_date: date
    frequency: BillFrequency = "monthly"
    category_id: int | None = None
    auto_repeat: bool = True
    notes: str | None = Field(default=None, max_length=1000)
    reminder_days: list[int] | None = Field(default=None, max_length=6)  # days before due; 0 = on the day; None = 7,3,1,0
    active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, v):
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name can't be blank.")
        return v

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v):
        return (v.strip() or None) if v is not None else None

    @field_validator("due_date")
    @classmethod
    def sane_date(cls, v):
        if not (2000 <= v.year <= 2100):
            raise ValueError("Due date looks wrong. Please check the year.")
        return v

    @field_validator("reminder_days")
    @classmethod
    def clean_reminders(cls, v):
        if v is None:
            return None
        if any(d < 0 or d > 60 for d in v):
            raise ValueError("Reminders must be between 0 and 60 days before the due date.")
        return sorted(set(v), reverse=True)


class PayIn(BaseModel):
    paid_on: date | None = None  # defaults to today (in the user's timezone)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)  # defaults to the bill amount
    create_transaction: bool = True  # also record the payment as an expense
    account_id: int | None = None
    payment_method: PaymentMethod = "other"


class BillOut(BaseModel):
    id: int
    name: str
    kind: str
    amount: Decimal
    category_id: int | None
    category: str | None
    due_date: date
    frequency: str
    auto_repeat: bool
    notes: str | None
    reminder_days: list[int]
    active: bool
    paid: bool
    last_paid: date | None
    status: str
    days_until: int
    monthly_equivalent: Decimal | None


class BillSummary(BaseModel):
    overdue_count: int
    overdue_total: Decimal
    due_next_7_days_total: Decimal
    monthly_commitment: Decimal


class BillList(BaseModel):
    items: list[BillOut]
    summary: BillSummary


class PayOut(BaseModel):
    bill: BillOut
    transaction_id: int | None
    debt_id: int | None = None  # set when the bill pays a tracked debt
    debt_remaining: Decimal | None = None
