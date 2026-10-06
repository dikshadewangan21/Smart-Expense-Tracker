from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.clock import user_today
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.schemas.transactions import PaymentMethod
from app.services import receipts as svc

router = APIRouter(prefix="/receipts", tags=["receipts"])

class ConfirmReceiptIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    date: date
    category_id: int | None = None
    payment_method: PaymentMethod = "other"
    account_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)

@router.post("/upload", summary="Upload a receipt image or document to parse with OCR")
async def upload_receipt(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if not content:
        raise HTTPException(422, "Uploaded file is empty.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(422, "Receipt file must be under 10MB.")

    return svc.parse_and_create_receipt(db, user, content, file.filename or "receipt.jpg")

@router.get("", summary="List all user uploaded receipts")
def list_receipts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_receipts(db, user.id)

@router.get("/{receipt_id}", summary="Get receipt details and parsed line items")
def get_receipt(receipt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = svc.get_receipt(db, user.id, receipt_id)
    if not r:
        raise HTTPException(404, "Receipt not found.")
    return svc.view_receipt(db, r)

@router.post("/{receipt_id}/confirm", summary="Confirm receipt details and create an expense transaction")
def confirm_receipt(
    receipt_id: int,
    body: ConfirmReceiptIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = svc.get_receipt(db, user.id, receipt_id)
    if not r:
        raise HTTPException(404, "Receipt not found.")
    return svc.confirm_receipt_as_transaction(
        db=db,
        user=user,
        receipt=r,
        merchant=body.merchant,
        amount=body.amount,
        tx_date=body.date,
        category_id=body.category_id,
        payment_method=body.payment_method,
        account_id=body.account_id,
        notes=body.notes,
    )
