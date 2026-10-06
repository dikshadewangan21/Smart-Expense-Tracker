from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Category, User
from app.services.categories import suggest_category_id
from app.services.periods import add_months, month_end

def parse_quick_add(text: str, user: User, today: date, db: Session) -> dict:
    raw = text.strip()
    low = raw.lower()

    tx_type = "expense"
    if any(k in low for k in ["salary", "received", "income", "got", "earned", "refund", "credit", "cashback"]):
        tx_type = "income"
    elif any(k in low for k in ["spent", "paid", "gave", "bought", "expense", "debited"]):
        tx_type = "expense"

    # Detect Date
    tx_date = today
    if "yesterday" in low:
        tx_date = today - timedelta(days=1)
    elif "day before yesterday" in low:
        tx_date = today - timedelta(days=2)
    else:
        # Check specific date like "on 15th", "on 2026-10-04", "on 5 oct"
        m_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw)
        if m_date:
            try:
                tx_date = date.fromisoformat(m_date.group(1))
            except ValueError:
                pass
        else:
            m_day = re.search(r"\bon\s+(\d{1,2})(?:st|nd|rd|th)?\b", low)
            if m_day:
                try:
                    day_val = int(m_day.group(1))
                    tx_date = today.replace(day=day_val)
                except ValueError:
                    pass

    # Detect Payment Method
    pm = "other"
    if "upi" in low:
        pm = "upi"
    elif "cash" in low:
        pm = "cash"
    elif "credit card" in low or "card" in low:
        pm = "credit_card"
    elif "debit card" in low:
        pm = "debit_card"
    elif "net banking" in low:
        pm = "net_banking"
    elif "bank transfer" in low or "neft" in low or "imps" in low:
        pm = "bank_transfer"

    # Extract Amount
    # e.g. rs. 250, ₹500, 250 rs, 45.50
    amount = Decimal("0")
    amount_matches = list(re.finditer(r"(?:(?:rs\.?|inr|₹|\$)\s*)?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2}))(?:\s*(?:rs|inr|bucks))?", low))
    clean_text = raw
    if amount_matches:
        # Choose the first sensible amount
        for match in amount_matches:
            val_str = match.group(1).replace(",", "")
            try:
                val = Decimal(val_str)
                if val > 0:
                    amount = val
                    # Remove the amount match from text for cleaner merchant detection
                    clean_text = clean_text[:match.start()] + " " + clean_text[match.end():]
                    break
            except InvalidOperation:
                pass

    # Extract merchant and category
    # Remove filler words
    stopwords = [
        "spent", "paid", "bought", "received", "earned", "yesterday", "today",
        "day before", "via", "using", "on", "at", "for", "from", "in", "with",
        "upi", "cash", "credit card", "card", "debit card", "rs", "inr", "rupees", "bucks"
    ]
    tokens = clean_text.split()
    filtered_tokens = []
    for t in tokens:
        sub = re.sub(r"[^\w\s]", "", t.lower())
        if sub not in stopwords and not sub.isdigit():
            filtered_tokens.append(t)

    merchant = " ".join(filtered_tokens).strip() or ("Income" if tx_type == "income" else "Expense")
    merchant = merchant[:160]

    cat_id = None
    if merchant and tx_type == "expense":
        cat_id = suggest_category_id(db, user.id, merchant, tx_type)

    return {
        "type": tx_type,
        "amount": amount,
        "merchant": merchant,
        "date": tx_date,
        "payment_method": pm,
        "category_id": cat_id,
        "notes": f"Quick added from: '{text}'",
    }

def parse_nl_search(query: str, today: date) -> dict:
    """Parses natural language search into query filters for transactions."""
    low = query.lower().strip()
    filters = {}

    if any(k in low for k in ["income", "received", "deposit"]):
        filters["type"] = "income"
    elif any(k in low for k in ["expense", "spent"]):
        filters["type"] = "expense"
    elif "transfer" in low:
        filters["type"] = "transfer"

    # Date ranges
    if "this month" in low:
        filters["date_from"] = today.replace(day=1)
        filters["date_to"] = today
    elif "last month" in low:
        prev = add_months(today.replace(day=1), -1)
        filters["date_from"] = prev
        filters["date_to"] = month_end(prev)
    elif "this year" in low:
        filters["date_from"] = date(today.year, 1, 1)
        filters["date_to"] = today
    elif "yesterday" in low:
        y = today - timedelta(days=1)
        filters["date_from"] = y
        filters["date_to"] = y
    elif "today" in low:
        filters["date_from"] = today
        filters["date_to"] = today

    # Amount filters
    m_above = re.search(r"(?:above|over|more than|greater than|>)\s*(?:rs\.?|₹|\$)?\s*([0-9]+(?:\.[0-9]+)?)", low)
    if m_above:
        filters["min_amount"] = Decimal(m_above.group(1))

    m_below = re.search(r"(?:below|under|less than|<)\s*(?:rs\.?|₹|\$)?\s*([0-9]+(?:\.[0-9]+)?)", low)
    if m_below:
        filters["max_amount"] = Decimal(m_below.group(1))

    # Payment methods
    for pm in ["upi", "cash", "credit_card", "debit_card", "bank_transfer", "net_banking", "wallet"]:
        if pm in low or pm.replace("_", " ") in low:
            filters["payment_method"] = pm
            break

    # Search keyword
    # Remove parsed phrases
    cleaned = re.sub(r"\b(above|over|more than|below|under|less than|this month|last month|this year|today|yesterday|income|expense|transfer|upi|cash|credit card|debit card)\b", "", low)
    cleaned = re.sub(r"[0-9]+(?:\.[0-9]+)?", "", cleaned).strip()
    if cleaned:
        filters["q"] = " ".join(cleaned.split())

    return filters
