import os
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Receipt, ReceiptItem, Transaction, User
from app.providers.ocr import get_ocr_provider
from app.services.categories import suggest_category_id

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "receipts")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def parse_and_create_receipt(db: Session, user: User, file_bytes: bytes, filename: str) -> dict:
    storage_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, storage_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    parser = get_ocr_provider()
    parsed = parser.extract_receipt(file_bytes, filename)

    receipt = Receipt(
        user_id=user.id,
        storage_key=storage_filename,
        merchant=parsed.merchant,
        total=parsed.total,
        tax=parsed.tax,
        receipt_date=parsed.date or date.today(),
        status="pending_review",
    )
    db.add(receipt)
    db.flush()

    for item in parsed.items:
        db.add(ReceiptItem(receipt_id=receipt.id, name=item.name, amount=item.amount))
    db.commit()

    return view_receipt(db, receipt)

def view_receipt(db: Session, receipt: Receipt) -> dict:
    items = db.scalars(select(ReceiptItem).where(ReceiptItem.receipt_id == receipt.id)).all()
    suggested_cat_id = suggest_category_id(db, receipt.user_id, receipt.merchant, "expense") if receipt.merchant else None
    return {
        "id": receipt.id,
        "storage_key": receipt.storage_key,
        "merchant": receipt.merchant,
        "total": receipt.total,
        "tax": receipt.tax,
        "receipt_date": receipt.receipt_date,
        "status": receipt.status,
        "suggested_category_id": suggested_cat_id,
        "items": [{"id": i.id, "name": i.name, "amount": i.amount} for i in items],
        "created_at": receipt.created_at,
    }

def list_receipts(db: Session, user_id: int) -> list[dict]:
    receipts = db.scalars(select(Receipt).where(Receipt.user_id == user_id).order_by(Receipt.id.desc())).all()
    return [view_receipt(db, r) for r in receipts]

def get_receipt(db: Session, user_id: int, receipt_id: int) -> Receipt | None:
    return db.scalar(select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user_id))

def confirm_receipt_as_transaction(
    db: Session,
    user: User,
    receipt: Receipt,
    merchant: str,
    amount: Decimal,
    tx_date: date,
    category_id: int | None = None,
    payment_method: str = "other",
    account_id: int | None = None,
    notes: str | None = None,
) -> dict:
    if receipt.status == "confirmed":
        existing_tx = db.scalar(select(Transaction).where(Transaction.receipt_id == receipt.id))
        if existing_tx:
            return {"transaction_id": existing_tx.id, "receipt_id": receipt.id}

    tx = Transaction(
        user_id=user.id,
        type="expense",
        amount=amount,
        currency=user.currency,
        category_id=category_id,
        merchant=merchant,
        date=tx_date,
        payment_method=payment_method,
        account_id=account_id,
        notes=notes or f"Imported from receipt #{receipt.id}",
        source="ocr",
        receipt_id=receipt.id,
    )
    db.add(tx)
    receipt.status = "confirmed"
    receipt.merchant = merchant
    receipt.total = amount
    receipt.receipt_date = tx_date
    db.commit()

    return {"transaction_id": tx.id, "receipt_id": receipt.id}
