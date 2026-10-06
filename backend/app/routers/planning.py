"""Accounts, categories and monthly budgets."""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import Account, Budget, BudgetCategory, Category, User
from app.routers.dashboard import user_today
from app.services.dashboard import budget_status, month_start

router = APIRouter(tags=["planning"])
Money = Field(max_digits=12, decimal_places=2)


# ---- accounts ----
class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["cash", "bank", "wallet", "credit_card", "investment", "property", "other"]
    opening_balance: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=2)


class AccountOut(AccountIn):
    id: int
    archived: bool
    model_config = {"from_attributes": True}


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(include_archived: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Account).where(Account.user_id == user.id)
    if not include_archived:
        q = q.where(Account.archived.is_(False))
    return db.scalars(q.order_by(Account.id)).all()


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acc = Account(user_id=user.id, **body.model_dump())
    db.add(acc)
    db.commit()
    return acc


@router.delete("/accounts/{account_id}", status_code=204, summary="Archive an account (history is kept)")
def archive_account(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acc = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if acc is None:
        raise HTTPException(404, "Account not found.")
    acc.archived = True
    db.commit()


# ---- categories ----
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["expense", "income"] = "expense"
    essential: bool = False


class CategoryOut(CategoryIn):
    id: int
    model_config = {"from_attributes": True}


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Category).where(Category.user_id == user.id).order_by(Category.kind, Category.name)).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = body.name.strip()
    if db.scalar(select(Category.id).where(Category.user_id == user.id, Category.name == name, Category.kind == body.kind)):
        raise HTTPException(409, "You already have a category with that name.")
    cat = Category(user_id=user.id, name=name, kind=body.kind, essential=body.essential)
    db.add(cat)
    db.commit()
    return cat


# ---- budgets ----
class BudgetLine(BaseModel):
    category_id: int
    limit_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class BudgetIn(BaseModel):
    month: date  # any day in the month; normalised to the 1st
    name: str = Field(default="Monthly budget", max_length=120)
    total_limit: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    rollover: bool = False
    categories: list[BudgetLine] = Field(default_factory=list, max_length=50)


@router.get("/budgets", summary="Budget for a month with live usage (defaults to the current month)")
def get_budget(month: date | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = month_start(month or user_today(user))
    status = budget_status(db, user.id, m)
    return {"month": m, "budget": status}


@router.post("/budgets", status_code=201, summary="Create or replace the budget for a month")
def upsert_budget(body: BudgetIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = month_start(body.month)
    ids = [line.category_id for line in body.categories]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Each category can appear only once in a budget.")
    owned = set(db.scalars(select(Category.id).where(Category.user_id == user.id, Category.kind == "expense",
                                                     Category.id.in_(ids)))) if ids else set()
    if owned != set(ids):
        raise HTTPException(422, "One or more budget categories don't exist.")
    if sum((line.limit_amount for line in body.categories), Decimal("0")) > body.total_limit:
        raise HTTPException(422, "Category limits add up to more than the total budget.")
    budget = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.month == m))
    if budget is None:
        budget = Budget(user_id=user.id, month=m, name=body.name, total_limit=body.total_limit, rollover=body.rollover)
        db.add(budget)
        db.flush()
    else:
        budget.name, budget.total_limit, budget.rollover = body.name, body.total_limit, body.rollover
        db.query(BudgetCategory).filter(BudgetCategory.budget_id == budget.id).delete()
    for line in body.categories:
        db.add(BudgetCategory(budget_id=budget.id, category_id=line.category_id, limit_amount=line.limit_amount))
    db.commit()
    return {"month": m, "budget": budget_status(db, user.id, m)}
