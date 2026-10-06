import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Account, Category, Import, Transaction, User
from app.services.categories import suggest_category_id

def _hash_tx(user_id: int, tx_date: date, amount: Decimal, merchant: str | None, tx_type: str, account_id: int | None) -> str:
    norm_merchant = (merchant or "").strip().lower()
    raw = f"{user_id}:{tx_date.isoformat()}:{amount:.2f}:{norm_merchant}:{tx_type}:{account_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _parse_date(s: str) -> date | None:
    s = s.strip()
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None

def _parse_amount(s: str) -> Decimal | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.-]", "", s.strip())
    try:
        val = Decimal(cleaned)
        return abs(val)
    except InvalidOperation:
        return None

def preview_csv(file_content: str, max_rows: int = 5) -> dict:
    f = io.StringIO(file_content)
    reader = csv.reader(f)
    try:
        header = next(reader)
    except StopIteration:
        return {"headers": [], "rows": [], "detected_mapping": {}}

    sample_rows = []
    for _ in range(max_rows):
        try:
            row = next(reader)
            if row:
                sample_rows.append(row)
        except StopIteration:
            break

    detected = {}
    for idx, col in enumerate(header):
        low = col.lower().strip()
        if any(k in low for k in ["date", "txn date", "transaction date", "time"]):
            detected.setdefault("date", idx)
        elif any(k in low for k in ["description", "narration", "merchant", "particulars", "payee", "remarks"]):
            detected.setdefault("merchant", idx)
        elif any(k in low for k in ["amount", "txn amount", "net", "total"]):
            detected.setdefault("amount", idx)
        elif any(k in low for k in ["debit", "withdrawal"]):
            detected.setdefault("debit", idx)
        elif any(k in low for k in ["credit", "deposit"]):
            detected.setdefault("credit", idx)
        elif any(k in low for k in ["category", "cat"]):
            detected.setdefault("category", idx)
        elif any(k in low for k in ["type", "dr/cr"]):
            detected.setdefault("type", idx)
        elif any(k in low for k in ["mode", "payment method", "channel"]):
            detected.setdefault("payment_method", idx)

    return {
        "headers": header,
        "sample_rows": sample_rows,
        "detected_mapping": detected,
    }

def execute_import(
    db: Session,
    user: User,
    file_content: str,
    filename: str,
    column_mapping: dict[str, int],
    account_id: int | None = None,
    default_payment_method: str = "other",
) -> dict:
    f = io.StringIO(file_content)
    reader = csv.reader(f)
    try:
        _ = next(reader)
    except StopIteration:
        return {"imported": 0, "duplicates": 0, "errors": 0, "total": 0}

    date_idx = column_mapping.get("date")
    merchant_idx = column_mapping.get("merchant")
    amount_idx = column_mapping.get("amount")
    debit_idx = column_mapping.get("debit")
    credit_idx = column_mapping.get("credit")
    category_idx = column_mapping.get("category")
    type_idx = column_mapping.get("type")
    pm_idx = column_mapping.get("payment_method")

    cat_map = {c.name.lower(): c.id for c in db.scalars(select(Category).where(Category.user_id == user.id))}
    existing_hashes = set(db.scalars(select(Transaction.import_hash).where(
        Transaction.user_id == user.id, Transaction.import_hash.is_not(None)
    )))

    imported_count = 0
    duplicate_count = 0
    error_count = 0
    total_count = 0

    to_insert: list[Transaction] = []

    for row in reader:
        if not row or all(c.strip() == "" for c in row):
            continue
        total_count += 1

        tx_date = None
        if date_idx is not None and date_idx < len(row):
            tx_date = _parse_date(row[date_idx])
        if not tx_date:
            error_count += 1
            continue

        merchant = None
        if merchant_idx is not None and merchant_idx < len(row):
            merchant = " ".join(row[merchant_idx].split())[:160] or None

        tx_type = "expense"
        amount = None

        if debit_idx is not None and debit_idx < len(row) and credit_idx is not None and credit_idx < len(row):
            deb = _parse_amount(row[debit_idx])
            crd = _parse_amount(row[credit_idx])
            if crd and crd > 0:
                tx_type = "income"
                amount = crd
            elif deb and deb > 0:
                tx_type = "expense"
                amount = deb
        elif amount_idx is not None and amount_idx < len(row):
            raw_amt_str = row[amount_idx]
            amt = _parse_amount(raw_amt_str)
            if amt and amt > 0:
                amount = amt
                if type_idx is not None and type_idx < len(row):
                    t_str = row[type_idx].lower()
                    if any(k in t_str for k in ["cr", "credit", "income", "deposit"]):
                        tx_type = "income"
                elif "-" in raw_amt_str:
                    tx_type = "expense"

        if not amount or amount <= 0:
            error_count += 1
            continue

        # Check deduplication hash
        h = _hash_tx(user.id, tx_date, amount, merchant, tx_type, account_id)
        if h in existing_hashes:
            duplicate_count += 1
            continue

        existing_hashes.add(h)

        cat_id = None
        if category_idx is not None and category_idx < len(row):
            c_name = row[category_idx].strip().lower()
            cat_id = cat_map.get(c_name)

        if cat_id is None and merchant and tx_type == "expense":
            cat_id = suggest_category_id(db, user.id, merchant, tx_type)

        pm = default_payment_method
        if pm_idx is not None and pm_idx < len(row):
            raw_pm = row[pm_idx].strip().lower()
            for cand in ["upi", "cash", "credit_card", "debit_card", "bank_transfer", "net_banking", "wallet"]:
                if cand in raw_pm:
                    pm = cand
                    break

        tx = Transaction(
            user_id=user.id,
            type=tx_type,
            amount=amount,
            currency=user.currency,
            category_id=cat_id,
            merchant=merchant,
            date=tx_date,
            payment_method=pm,
            account_id=account_id,
            source="csv",
            import_hash=h,
        )
        to_insert.append(tx)
        imported_count += 1

    if to_insert:
        db.add_all(to_insert)

    import_rec = Import(
        user_id=user.id,
        kind="csv",
        filename=filename,
        rows_total=total_count,
        rows_imported=imported_count,
        rows_duplicate=duplicate_count,
        status="done" if error_count == 0 else "partial",
    )
    db.add(import_rec)
    db.commit()

    return {
        "import_id": import_rec.id,
        "rows_total": total_count,
        "rows_imported": imported_count,
        "rows_duplicate": duplicate_count,
        "rows_errors": error_count,
    }

def list_imports(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(select(Import).where(Import.user_id == user_id).order_by(Import.id.desc())).all()
    return [{
        "id": r.id,
        "kind": r.kind,
        "filename": r.filename,
        "rows_total": r.rows_total,
        "rows_imported": r.rows_imported,
        "rows_duplicate": r.rows_duplicate,
        "status": r.status,
        "created_at": r.created_at,
    } for r in rows]
