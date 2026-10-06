from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
import json

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.services import imports as svc

router = APIRouter(prefix="/imports", tags=["imports"])

@router.post("/preview", summary="Preview CSV rows and detect column mappings")
async def preview_csv(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    content = await file.read()
    if not content:
        raise HTTPException(422, "File is empty.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin1")
        except Exception:
            raise HTTPException(422, "Could not decode file as CSV text.")

    return svc.preview_csv(text)

@router.post("/execute", summary="Execute CSV import with specified column mappings")
async def execute_csv_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),  # JSON string of column mappings
    account_id: int | None = Form(None),
    default_payment_method: str = Form("other"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if not content:
        raise HTTPException(422, "File is empty.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin1")
        except Exception:
            raise HTTPException(422, "Could not decode file as CSV text.")

    try:
        col_map = json.loads(mapping)
    except Exception:
        raise HTTPException(422, "Invalid JSON column mapping provided.")

    return svc.execute_import(
        db=db,
        user=user,
        file_content=text,
        filename=file.filename or "statement.csv",
        column_mapping=col_map,
        account_id=account_id,
        default_payment_method=default_payment_method,
    )

@router.get("", summary="List previous import runs and statistics")
def list_imports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_imports(db, user.id)
