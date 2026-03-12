from decimal import Decimal, InvalidOperation


def parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    cleaned = raw.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
