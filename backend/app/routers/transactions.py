from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import Account, AuditLog, Category, Tag, Transaction, TransactionTag, User
from app.routers.dashboard import user_today
from app.schemas.transactions import PaymentMethod, SplitIn, TxIn, TxOut, TxPage, TxType
from app.services.categories import learn_rule, suggest_category_id

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _like(s: str) -> str:
    return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _check_refs(db: Session, user: User, tx_type: str, category_id: int | None, account_id: int | None,
                to_account_id: int | None = None) -> None:
    """Every referenced row must belong to the caller. Returns 404-style errors without leaking existence."""
    if tx_type == "transfer":
        if account_id is None or to_account_id is None:
            raise HTTPException(422, "A transfer needs both a 'from' and a 'to' account.")
        if account_id == to_account_id:
            raise HTTPException(422, "A transfer must move money between two different accounts.")
        if category_id is not None:
            raise HTTPException(422, "Transfers don't have a category.")
    elif to_account_id is not None:
        raise HTTPException(422, "Only a transfer has a destination account.")
    if to_account_id is not None:
        owned = db.scalar(select(Account.id).where(Account.id == to_account_id, Account.user_id == user.id))
        if owned is None:
            raise HTTPException(422, "That account doesn't exist.")
    if category_id is not None:
        cat = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
        if cat is None:
            raise HTTPException(422, "That category doesn't exist.")
        if tx_type in ("income", "expense") and cat.kind != tx_type:
            raise HTTPException(422, f"That category is for {cat.kind}, not {tx_type}.")
    if account_id is not None:
        if db.scalar(select(Account.id).where(Account.id == account_id, Account.user_id == user.id)) is None:
            raise HTTPException(422, "That account doesn't exist.")


def _tags_for(db: Session, user_id: int, names: list[str]) -> list[Tag]:
    out = []
    for n in names:
        tag = db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.name == n))
        if tag is None:
            tag = Tag(user_id=user_id, name=n)
            db.add(tag)
            db.flush()
        out.append(tag)
    return out


def _set_tags(db: Session, tx: Transaction, names: list[str]) -> None:
    for link in db.scalars(select(TransactionTag).where(TransactionTag.transaction_id == tx.id)):
        db.delete(link)
    db.flush()
    for tag in _tags_for(db, tx.user_id, names):
        db.add(TransactionTag(transaction_id=tx.id, tag_id=tag.id))


def _out_many(db: Session, txs: list[Transaction]) -> list[TxOut]:
    if not txs:
        return []
    ids = [t.id for t in txs]
    cat_ids = {t.category_id for t in txs if t.category_id}
    cats = {c.id: c.name for c in db.scalars(select(Category).where(Category.id.in_(cat_ids)))} if cat_ids else {}
    tags: dict[int, list[str]] = {}
    for tid, name in db.execute(select(TransactionTag.transaction_id, Tag.name)
                                .join(Tag, Tag.id == TransactionTag.tag_id)
                                .where(TransactionTag.transaction_id.in_(ids))):
        tags.setdefault(tid, []).append(name)
    return [TxOut(id=t.id, type=t.type, amount=t.amount, currency=t.currency, category_id=t.category_id,
                  category=cats.get(t.category_id), subcategory=t.subcategory, merchant=t.merchant, date=t.date,
                  payment_method=t.payment_method, account_id=t.account_id, to_account_id=t.to_account_id, notes=t.notes,
                  tags=sorted(tags.get(t.id, [])), is_recurring=t.is_recurring, source=t.source) for t in txs]


def _get_owned(db: Session, user: User, tx_id: int) -> Transaction:
    tx = db.scalar(select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user.id))
    if tx is None:
        raise HTTPException(404, "Transaction not found.")
    return tx


@router.get("", response_model=TxPage, summary="List transactions (paginated, filterable)")
def list_transactions(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    q: str | None = Query(None, max_length=100), type: TxType | None = None,
    category_id: int | None = None, uncategorized: bool = False,
    merchant: str | None = Query(None, max_length=100), merchant_exact: str | None = Query(None, max_length=160),
    date_from: date | None = None, date_to: date | None = None,
    min_amount: Decimal | None = Query(None, ge=0), max_amount: Decimal | None = Query(None, ge=0),
    payment_method: PaymentMethod | None = None, account_id: int | None = None,
    tag: str | None = Query(None, max_length=50),
    sort: Literal["date", "amount", "merchant"] = "date", order: Literal["asc", "desc"] = "desc",
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    conds = [Transaction.user_id == user.id]
    if q:
        conds.append(or_(Transaction.merchant.ilike(_like(q), escape="\\"), Transaction.notes.ilike(_like(q), escape="\\")))
    if type:
        conds.append(Transaction.type == type)
    if category_id is not None:
        conds.append(Transaction.category_id == category_id)
    if uncategorized:
        conds.append(Transaction.category_id.is_(None))
    if merchant_exact:
        conds.append(func.lower(func.trim(Transaction.merchant)) == " ".join(merchant_exact.lower().split()))
    if merchant:
        conds.append(Transaction.merchant.ilike(_like(merchant), escape="\\"))
    if date_from:
        conds.append(Transaction.date >= date_from)
    if date_to:
        conds.append(Transaction.date <= date_to)
    if min_amount is not None:
        conds.append(Transaction.amount >= min_amount)
    if max_amount is not None:
        conds.append(Transaction.amount <= max_amount)
    if payment_method:
        conds.append(Transaction.payment_method == payment_method)
    if account_id is not None:
        conds.append(or_(Transaction.account_id == account_id, Transaction.to_account_id == account_id))
    if tag:
        conds.append(Transaction.id.in_(
            select(TransactionTag.transaction_id).join(Tag, Tag.id == TransactionTag.tag_id)
            .where(Tag.user_id == user.id, Tag.name == tag.strip().lower())))

    total = db.scalar(select(func.count()).select_from(Transaction).where(*conds))
    col = {"date": Transaction.date, "amount": Transaction.amount, "merchant": Transaction.merchant}[sort]
    ordering = [col.asc() if order == "asc" else col.desc(), Transaction.id.desc()]
    rows = db.scalars(select(Transaction).where(*conds).order_by(*ordering)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return TxPage(items=_out_many(db, list(rows)), total=total, page=page, page_size=page_size)


@router.post("", response_model=TxOut, status_code=201, summary="Create a transaction")
def create_transaction(body: TxIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_refs(db, user, body.type, body.category_id, body.account_id, body.to_account_id)
    category_id = body.category_id
    if category_id is None and body.type != "transfer":
        category_id = suggest_category_id(db, user.id, body.merchant, body.type)
    tx = Transaction(user_id=user.id, type=body.type, amount=body.amount, currency=user.currency,
                     category_id=category_id, subcategory=body.subcategory, merchant=body.merchant, date=body.date,
                     payment_method=body.payment_method, account_id=body.account_id, to_account_id=body.to_account_id,
                     notes=body.notes, is_recurring=body.is_recurring and body.type != "transfer", source="manual")
    db.add(tx)
    db.flush()
    _set_tags(db, tx, body.tags)
    db.commit()
    return _out_many(db, [tx])[0]


@router.get("/{tx_id}", response_model=TxOut)
def get_transaction(tx_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out_many(db, [_get_owned(db, user, tx_id)])[0]


@router.put("/{tx_id}", response_model=TxOut, summary="Update a transaction; set always_categorize to remember the merchant's category")
def update_transaction(tx_id: int, body: TxIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tx = _get_owned(db, user, tx_id)
    _check_refs(db, user, body.type, body.category_id, body.account_id, body.to_account_id)
    changed_category = body.category_id is not None and body.category_id != tx.category_id
    for f in ("type", "amount", "category_id", "subcategory", "merchant", "date", "payment_method",
              "account_id", "to_account_id", "notes", "is_recurring"):
        setattr(tx, f, getattr(body, f))
    _set_tags(db, tx, body.tags)
    if body.always_categorize and body.category_id is not None and tx.merchant and tx.type == "expense":
        learn_rule(db, user.id, tx.merchant, body.category_id)
    elif changed_category and not body.always_categorize:
        pass  # one-off correction; no rule learned unless the user asks
    db.commit()
    return _out_many(db, [tx])[0]


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tx = _get_owned(db, user, tx_id)
    db.add(AuditLog(user_id=user.id, action="transaction_delete", detail=f"id={tx.id} amount={tx.amount}"))
    db.query(TransactionTag).filter(TransactionTag.transaction_id == tx.id).delete()
    db.delete(tx)
    db.commit()


@router.post("/{tx_id}/duplicate", response_model=TxOut, status_code=201, summary="Copy a transaction dated today")
def duplicate_transaction(tx_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    src = _get_owned(db, user, tx_id)
    copy = Transaction(user_id=user.id, type=src.type, amount=src.amount, currency=src.currency,
                       category_id=src.category_id, subcategory=src.subcategory, merchant=src.merchant,
                       date=user_today(user), payment_method=src.payment_method, account_id=src.account_id, to_account_id=src.to_account_id,
                       notes=src.notes, is_recurring=src.is_recurring, source="manual")
    db.add(copy)
    db.flush()
    names = [n for (n,) in db.execute(select(Tag.name).join(TransactionTag, TransactionTag.tag_id == Tag.id)
                                      .where(TransactionTag.transaction_id == src.id))]
    _set_tags(db, copy, names)
    db.commit()
    return _out_many(db, [copy])[0]


@router.post("/{tx_id}/split", response_model=list[TxOut], summary="Split into parts that sum exactly to the original amount")
def split_transaction(tx_id: int, body: SplitIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    src = _get_owned(db, user, tx_id)
    if src.type == "transfer":
        raise HTTPException(422, "Transfers can't be split.")
    total = sum((p.amount for p in body.parts), Decimal("0"))
    if total != Decimal(src.amount):
        raise HTTPException(422, f"The parts add up to {total}, but the transaction is {src.amount}. They must match exactly.")
    for p in body.parts:
        _check_refs(db, user, src.type, p.category_id, None)
    names = [n for (n,) in db.execute(select(Tag.name).join(TransactionTag, TransactionTag.tag_id == Tag.id)
                                      .where(TransactionTag.transaction_id == src.id))]
    result = []
    for i, p in enumerate(body.parts):
        if i == 0:
            tx = src
            tx.amount, tx.category_id = p.amount, p.category_id
            if p.notes:
                tx.notes = p.notes
        else:
            tx = Transaction(user_id=user.id, type=src.type, amount=p.amount, currency=src.currency,
                             category_id=p.category_id, merchant=src.merchant, date=src.date,
                             payment_method=src.payment_method, account_id=src.account_id,
                             notes=p.notes or src.notes, source=src.source)
            db.add(tx)
            db.flush()
            _set_tags(db, tx, names)
        result.append(tx)
    db.add(AuditLog(user_id=user.id, action="transaction_split", detail=f"id={src.id} parts={len(body.parts)}"))
    db.commit()
    return _out_many(db, result)
