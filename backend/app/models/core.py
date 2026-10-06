from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint, false, true)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

Money = Numeric(14, 2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


def uid_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class User(Base, Timestamps):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120), default="")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", server_default="Asia/Kolkata")
    monthly_income: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    income_frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    monthly_savings_target: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    budgeting_style: Mapped[str] = mapped_column(String(30), default="balanced")
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_prefs: Mapped[dict] = mapped_column(JSON, default=dict)


class RefreshToken(Base, Timestamps):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Account(Base, Timestamps):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # cash|bank|wallet|credit_card|investment|property|other
    opening_balance: Mapped[Decimal] = mapped_column(Money, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class AccountValuation(Base, Timestamps):
    """A dated "this account was worth X at the end of that day" entry, for accounts whose value is not just
    the sum of transactions (investments, property). Balance after a valuation = value + later transactions."""
    __tablename__ = "account_valuations"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Money)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    __table_args__ = (UniqueConstraint("account_id", "date"),)


class Category(Base, Timestamps):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10), default="expense")  # expense|income
    essential: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("user_id", "name", "kind"),)


class Tag(Base, Timestamps):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(50))
    __table_args__ = (UniqueConstraint("user_id", "name"),)


class CategoryRule(Base, Timestamps):
    """Learned from user corrections: 'always categorize this merchant as ...'."""
    __tablename__ = "category_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    merchant_key: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("user_id", "merchant_key"),)


class Transaction(Base, Timestamps):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    type: Mapped[str] = mapped_column(String(10))  # income|expense|transfer
    amount: Mapped[Decimal] = mapped_column(Money)  # always positive; sign derives from type
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(80), nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(160), nullable=True)
    date: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str] = mapped_column(String(20), default="other")
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    # Transfers only: the account the money moves INTO (account_id is the one it leaves).
    to_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|csv|ocr|quick_add|demo
    import_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        Index("ix_tx_user_date", "user_id", "date"),
        Index("ix_tx_user_category", "user_id", "category_id"),
        Index("ix_tx_user_merchant", "user_id", "merchant"),
        Index("ix_tx_user_pm", "user_id", "payment_method"),
        UniqueConstraint("user_id", "import_hash"),
    )


class TransactionTag(Base):
    __tablename__ = "transaction_tags"
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Budget(Base, Timestamps):
    __tablename__ = "budgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(120), default="Monthly budget")
    month: Mapped[date] = mapped_column(Date)  # first day of month
    total_limit: Mapped[Decimal] = mapped_column(Money)
    rollover: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index("ix_budget_user_month", "user_id", "month"),)


class BudgetCategory(Base, Timestamps):
    __tablename__ = "budget_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    limit_amount: Mapped[Decimal] = mapped_column(Money)
    __table_args__ = (UniqueConstraint("budget_id", "category_id"),)


class RecurringTransaction(Base, Timestamps):
    """A confirmed (or ignored) recurring pattern. Candidates are computed on demand and only
    persisted when the user confirms or ignores them. One row per (user, type, merchant_key)."""
    __tablename__ = "recurring_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    type: Mapped[str] = mapped_column(String(10), default="expense", server_default="expense")  # expense|income
    merchant: Mapped[str] = mapped_column(String(160))
    merchant_key: Mapped[str] = mapped_column(String(160), default="", server_default="")
    amount: Mapped[Decimal] = mapped_column(Money)
    frequency: Mapped[str] = mapped_column(String(20))  # weekly|biweekly|monthly|quarterly|yearly
    last_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    anchor_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # day of month to land on
    next_expected: Mapped[date | None] = mapped_column(Date, nullable=True)  # legacy; next date is computed
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="confirmed")  # confirmed|paused|ignored
    reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    source: Mapped[str] = mapped_column(String(10), default="detected", server_default="detected")  # detected|manual
    __table_args__ = (Index("uq_recurring_user_type_key", "user_id", "type", "merchant_key", unique=True),)


class Subscription(Base, Timestamps):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Money)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    next_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Bill(Base, Timestamps):
    __tablename__ = "bills"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="custom", server_default="custom")
    amount: Mapped[Decimal] = mapped_column(Money)
    due_date: Mapped[date] = mapped_column(Date, index=True)  # next unpaid due date
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")  # once|weekly|monthly|quarterly|yearly
    anchor_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # keeps "31st" bills on month-ends
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    auto_repeat: Mapped[bool] = mapped_column(Boolean, default=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)  # only meaningful for one-time bills
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_days: Mapped[list | None] = mapped_column(JSON, nullable=True)  # None = default [7, 3, 1, 0]
    last_paid: Mapped[date | None] = mapped_column(Date, nullable=True)


class Goal(Base, Timestamps):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30), default="custom")
    target_amount: Mapped[Decimal] = mapped_column(Money)
    current_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class GoalContribution(Base, Timestamps):
    __tablename__ = "goal_contributions"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)  # positive adds to the goal, negative is a withdrawal
    date: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Debt(Base, Timestamps):
    __tablename__ = "debts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # personal|education|credit_card|borrowed|lent
    principal: Mapped[Decimal] = mapped_column(Money)
    remaining: Mapped[Decimal] = mapped_column(Money)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    emi: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # when it began; None = assume it always existed
    # A bill that pays this debt: paying the bill also records a payment here (and the bill is not counted
    # as a "recurring payment" in the health score, since the debt-burden component already counts the EMI).
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bills.id", ondelete="SET NULL"), nullable=True)


class DebtPayment(Base, Timestamps):
    __tablename__ = "debt_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)  # cash that moved
    principal_paid: Mapped[Decimal] = mapped_column(Money)  # the part that reduced `remaining`; the rest was interest/fees
    date: Mapped[date] = mapped_column(Date)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)


class SharedGroup(Base, Timestamps):
    __tablename__ = "shared_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="friends")


class GroupMember(Base, Timestamps):
    __tablename__ = "group_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("shared_groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="invited")
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)


class GroupExpense(Base, Timestamps):
    __tablename__ = "group_expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("shared_groups.id", ondelete="CASCADE"), index=True)
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Money)
    description: Mapped[str] = mapped_column(String(200))
    date: Mapped[date] = mapped_column(Date)
    splits: Mapped[dict] = mapped_column(JSON, default=dict)  # {user_id: share_amount}
    settled: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base, Timestamps):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    kind: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key"),)


class Receipt(Base, Timestamps):
    __tablename__ = "receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    storage_key: Mapped[str] = mapped_column(String(255))
    merchant: Mapped[str | None] = mapped_column(String(160), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    tax: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="pending_review")


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Money)


class AIConversation(Base, Timestamps):
    __tablename__ = "ai_conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    title: Mapped[str] = mapped_column(String(160), default="")


class AIMessage(Base, Timestamps):
    __tablename__ = "ai_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    source_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Import(Base, Timestamps):
    __tablename__ = "imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = uid_fk()
    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(255))
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(15), default="done")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
