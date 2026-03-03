from typing import Any, Mapping


CSV_FORMULA_TRIGGER_CHARS = {"=", "+", "-", "@", "\t", "\r"}
_LEADING_WHITESPACE_CHARS = {" ", "\t", "\r", "\n"}


def neutralize_csv_cell(value: Any) -> str:
    """
    Return a CSV-safe cell value by neutralizing spreadsheet formula prefixes.
    """
    text = "" if value is None else str(value)
    if not text:
        return ""

    # Respect existing explicit text-prefixing.
    if text.startswith("'"):
        return text

    idx = 0
    text_len = len(text)
    while idx < text_len and text[idx] in _LEADING_WHITESPACE_CHARS:
        idx += 1

    if idx < text_len and text[idx] in CSV_FORMULA_TRIGGER_CHARS:
        return f"'{text}"
    return text


def neutralize_csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {key: neutralize_csv_cell(value) for key, value in row.items()}
