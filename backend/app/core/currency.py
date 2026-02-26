from typing import Optional

USD_CURRENCY = "USD"


def normalize_currency_code(value: Optional[str], *, default: str = USD_CURRENCY) -> str:
    normalized = str(value or default).strip().upper()
    if not normalized:
        return default
    return normalized


def require_usd_currency(value: Optional[str], *, field_name: str = "currency") -> str:
    normalized = normalize_currency_code(value)
    if normalized != USD_CURRENCY:
        raise ValueError(f"{field_name} must be USD")
    return normalized
