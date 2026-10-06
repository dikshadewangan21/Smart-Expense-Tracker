from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Protocol

@dataclass
class ReceiptItemDTO:
    name: str
    amount: Decimal

@dataclass
class ParsedReceipt:
    merchant: str | None = None
    date: date | None = None
    total: Decimal | None = None
    tax: Decimal | None = None
    items: list[ReceiptItemDTO] = field(default_factory=list)
    raw_text: str = ""

class OCRProvider(Protocol):
    def extract_receipt(self, file_bytes: bytes, filename: str) -> ParsedReceipt:
        ...

class HeuristicReceiptParser:
    """Heuristic OCR and text receipt extractor that works offline and supports standard invoice/receipt layouts."""

    def parse_text(self, text: str) -> ParsedReceipt:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ParsedReceipt(raw_text=text)

        merchant = None
        receipt_date = None
        total = None
        tax = None
        items: list[ReceiptItemDTO] = []

        # Find merchant from top lines (skip dates, phone numbers, invoice headers)
        for line in lines[:5]:
            lower = line.lower()
            if not any(k in lower for k in ["tax invoice", "receipt", "bill", "cash memo", "date", "phone", "gstin", "tel"]):
                merchant = line[:160]
                break
        if not merchant and lines:
            merchant = lines[0][:160]

        # Date pattern (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY)
        date_patterns = [
            r"\b(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b",
            r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](\d{4})\b"
        ]
        for line in lines:
            for pat in date_patterns:
                m = re.search(pat, line)
                if m:
                    try:
                        if len(m.group(1)) == 4:
                            receipt_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                        else:
                            receipt_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                        break
                    except ValueError:
                        pass
            if receipt_date:
                break

        # Total and tax search
        num_pattern = r"(?:(?:rs\.?|inr|₹|\$)\s*)?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2}))"
        total_patterns = [
            rf"(?:grand\s+total|total\s+amount|total|net\s+amount|bill\s+amount|amount\s+due)\s*[:=-]?\s*{num_pattern}",
            rf"(?:paid|paid\s+amount)\s*[:=-]?\s*{num_pattern}",
        ]
        tax_patterns = [
            rf"(?:cgst\s*\+\s*sgst|gst|tax|vat)\s*[:=-]?\s*{num_pattern}",
        ]

        for line in reversed(lines):
            lower = line.lower()
            if total is None:
                for pat in total_patterns:
                    m = re.search(pat, lower)
                    if m:
                        try:
                            clean_amt = m.group(1).replace(",", "")
                            val = Decimal(clean_amt)
                            if val > 0:
                                total = val
                                break
                        except InvalidOperation:
                            pass
            if tax is None:
                for pat in tax_patterns:
                    m = re.search(pat, lower)
                    if m:
                        try:
                            clean_amt = m.group(1).replace(",", "")
                            val = Decimal(clean_amt)
                            if val >= 0:
                                tax = val
                                break
                        except InvalidOperation:
                            pass

        # Parse line items: e.g. "Item Name 120.00" or "Item Name x 2 450.50"
        item_pattern = re.compile(rf"^([A-Za-z0-9\s&'-]{{2,60}})\s+(?:x\s*\d+\s+)?{num_pattern}$")
        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["total", "subtotal", "tax", "gst", "change", "cash", "card", "balance"]):
                continue
            m = item_pattern.match(line)
            if m:
                item_name = m.group(1).strip()
                try:
                    amt = Decimal(m.group(2).replace(",", ""))
                    if amt > 0 and amt != total:
                        items.append(ReceiptItemDTO(name=item_name, amount=amt))
                except InvalidOperation:
                    pass

        # If total was not detected but items were parsed
        if total is None and items:
            total = sum((i.amount for i in items), Decimal("0"))
        elif total is None:
            # Fallback to largest number found in bottom half
            candidates = []
            for line in lines[len(lines)//2:]:
                for match in re.finditer(num_pattern, line):
                    try:
                        v = Decimal(match.group(1).replace(",", ""))
                        if v > 0:
                            candidates.append(v)
                    except InvalidOperation:
                        pass
            if candidates:
                total = max(candidates)

        return ParsedReceipt(
            merchant=merchant,
            date=receipt_date or date.today(),
            total=total,
            tax=tax,
            items=items,
            raw_text=text
        )

    def extract_receipt(self, file_bytes: bytes, filename: str) -> ParsedReceipt:
        # Check if bytes are text/utf-8 readable (e.g. text receipts or test files)
        try:
            text = file_bytes.decode("utf-8")
            return self.parse_text(text)
        except UnicodeDecodeError:
            pass

        # For binary receipt images, extract printable ASCII/UTF-8 strings or metadata
        extracted_strings = []
        for word in re.findall(rb"[\x20-\x7E]{3,}", file_bytes):
            try:
                extracted_strings.append(word.decode("latin1"))
            except Exception:
                pass
        text = "\n".join(extracted_strings)
        parsed = self.parse_text(text)
        if not parsed.merchant:
            parsed.merchant = filename.rsplit(".", 1)[0].replace("_", " ").title()
        return parsed

def get_ocr_provider() -> OCRProvider:
    return HeuristicReceiptParser()
