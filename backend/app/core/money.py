from decimal import Decimal


def _indian_group(int_part: str) -> str:
    if len(int_part) <= 3:
        return int_part
    head, tail = int_part[:-3], int_part[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def fmt_money(amount, currency: str = "INR") -> str:
    """₹1,23,456 for INR (Indian digit grouping); 'USD 1,234.50' style otherwise.
    Whole amounts are shown without decimals, others with two."""
    d = Decimal(str(amount)).quantize(Decimal("0.01"))
    neg = d < 0
    d = abs(d)
    whole, frac = divmod(d, 1)
    int_str = str(int(whole))
    frac_str = f"{frac:.2f}"[1:]  # ".50"
    show_frac = frac != 0
    if currency == "INR":
        body = _indian_group(int_str) + (frac_str if show_frac else "")
        out = "₹" + body
    else:
        body = f"{int(whole):,}" + (frac_str if show_frac else "")
        out = f"{currency} {body}"
    return "-" + out if neg else out
