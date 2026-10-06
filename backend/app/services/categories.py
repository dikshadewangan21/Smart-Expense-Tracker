"""Default categories and deterministic merchant -> category matching.

Matching order for a new transaction without an explicit category:
  1. the user's learned rule for that merchant (from a past correction)
  2. built-in keyword table below
  3. otherwise left uncategorized (the AI categorizer in Phase 6 will only ever be a suggestion)
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Category, CategoryRule

DEFAULT_EXPENSE = {  # name: essential?
    "Food": False, "Groceries": True, "Transport": True, "Shopping": False, "Entertainment": False,
    "Bills": True, "Rent": True, "Health": True, "Education": True, "Travel": False,
    "EMI & Loans": True, "Subscriptions": False, "Other": False,
}
DEFAULT_INCOME = ["Salary", "Freelance", "Interest", "Gift", "Other income"]

MERCHANT_KEYWORDS = {
    "Food": ["swiggy", "zomato", "dominos", "mcdonald", "kfc", "starbucks", "cafe", "restaurant"],
    "Groceries": ["bigbasket", "blinkit", "zepto", "dmart", "reliance smart", "grofers", "instamart"],
    "Transport": ["uber", "ola", "rapido", "irctc", "metro", "petrol", "fuel", "indian oil"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho"],
    "Entertainment": ["bookmyshow", "pvr", "inox"],
    "Subscriptions": ["netflix", "spotify", "hotstar", "prime video", "youtube premium"],
    "Bills": ["airtel", "jio", "vodafone", "bsnl", "electricity", "broadband"],
    "Health": ["apollo", "pharmeasy", "1mg", "medplus", "hospital"],
}


def merchant_key(merchant: str | None) -> str:
    return " ".join((merchant or "").lower().split())


def seed_default_categories(db: Session, user_id: int) -> None:
    for name, essential in DEFAULT_EXPENSE.items():
        db.add(Category(user_id=user_id, name=name, kind="expense", essential=essential))
    for name in DEFAULT_INCOME:
        db.add(Category(user_id=user_id, name=name, kind="income"))


def suggest_category_id(db: Session, user_id: int, merchant: str | None, tx_type: str) -> int | None:
    key = merchant_key(merchant)
    if not key or tx_type != "expense":
        return None
    rule = db.scalar(select(CategoryRule).where(CategoryRule.user_id == user_id, CategoryRule.merchant_key == key))
    if rule:
        return rule.category_id
    for cat_name, words in MERCHANT_KEYWORDS.items():
        if any(w in key for w in words):
            cat = db.scalar(select(Category).where(Category.user_id == user_id, Category.name == cat_name,
                                                   Category.kind == "expense"))
            if cat:
                return cat.id
    return None


def learn_rule(db: Session, user_id: int, merchant: str | None, category_id: int) -> None:
    key = merchant_key(merchant)
    if not key:
        return
    rule = db.scalar(select(CategoryRule).where(CategoryRule.user_id == user_id, CategoryRule.merchant_key == key))
    if rule:
        rule.category_id = category_id
    else:
        db.add(CategoryRule(user_id=user_id, merchant_key=key, category_id=category_id))
