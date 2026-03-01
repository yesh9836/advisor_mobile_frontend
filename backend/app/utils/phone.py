import re
from typing import Optional

_ALPHA_PATTERN = re.compile(r"[A-Za-z]")
_DIGIT_PATTERN = re.compile(r"\D+")


def normalize_phone_number(value: Optional[str]) -> Optional[str]:
    """
    Normalize common phone input into a Twilio-friendly representation.

    Behavior is intentionally conservative:
    - Blank input -> None.
    - US 10-digit input -> +1XXXXXXXXXX.
    - US 11-digit input starting with 1 -> +1XXXXXXXXXX.
    - Explicit international input starting with '+' and 8-15 digits -> +<digits>.
    - Any other format is returned trimmed (no destructive rewrite).
    """
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    # Preserve non-phone tokens used by tests/fixtures and legacy data flows.
    if _ALPHA_PATTERN.search(raw):
        return raw

    digits_only = _DIGIT_PATTERN.sub("", raw)
    if not digits_only:
        return raw

    if raw.startswith("+"):
        if 8 <= len(digits_only) <= 15:
            return f"+{digits_only}"
        return raw

    if len(digits_only) == 10:
        return f"+1{digits_only}"
    if len(digits_only) == 11 and digits_only.startswith("1"):
        return f"+{digits_only}"

    return raw
