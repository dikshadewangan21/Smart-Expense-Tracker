from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PaymentMethod = Literal["upi", "cash", "debit_card", "credit_card", "bank_transfer", "wallet", "net_banking", "other"]
TxType = Literal["income", "expense", "transfer"]
Amount = Decimal


class TxIn(BaseModel):
    type: TxType
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category_id: int | None = None
    subcategory: str | None = Field(default=None, max_length=80)
    merchant: str | None = Field(default=None, max_length=160)
    date: date
    payment_method: PaymentMethod = "other"
    account_id: int | None = None  # for a transfer: the account the money leaves
    to_account_id: int | None = None  # transfers only: the account the money goes into
    notes: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=10)
    is_recurring: bool = False
    always_categorize: bool = False  # update only: remember merchant -> category

    @field_validator("merchant", "subcategory", "notes")
    @classmethod
    def strip_blank(cls, v):
        if v is None:
            return None
        v = " ".join(v.split())  # collapse inner whitespace so merchant matching is exact
        return v or None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v):
        out = []
        for t in v:
            t = t.strip().lower()[:50]
            if t and t not in out:
                out.append(t)
        return out


class TxOut(BaseModel):
    id: int
    type: str
    amount: Decimal
    currency: str
    category_id: int | None
    category: str | None
    subcategory: str | None
    merchant: str | None
    date: date
    payment_method: str
    account_id: int | None
    to_account_id: int | None = None
    notes: str | None
    tags: list[str]
    is_recurring: bool
    source: str


class TxPage(BaseModel):
    items: list[TxOut]
    total: int
    page: int
    page_size: int


class SplitPart(BaseModel):
    category_id: int | None = None
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    notes: str | None = Field(default=None, max_length=1000)


class SplitIn(BaseModel):
    parts: list[SplitPart] = Field(min_length=2, max_length=20)
