import json
from pathlib import Path
from typing import Final


_REPO_ROOT = Path(__file__).resolve().parents[3]
_US_STATE_CONTRACT_PATH = _REPO_ROOT / "shared" / "us_states.json"


def _load_us_state_contract() -> tuple[tuple[str, str], ...]:
    try:
        raw_entries = json.loads(_US_STATE_CONTRACT_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"US state contract file is missing: {_US_STATE_CONTRACT_PATH}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"US state contract file is not valid JSON: {_US_STATE_CONTRACT_PATH}"
        ) from exc

    if not isinstance(raw_entries, list):
        raise RuntimeError("US state contract must be a JSON array")

    normalized_entries: list[tuple[str, str]] = []
    seen_codes: set[str] = set()
    seen_labels: set[str] = set()

    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise RuntimeError("Each US state contract entry must be an object")

        code = entry.get("code")
        label = entry.get("label")
        if not isinstance(code, str) or not isinstance(label, str):
            raise RuntimeError("Each US state contract entry must include string code and label")

        normalized_code = code.strip().upper()
        normalized_label = label.strip()
        if len(normalized_code) != 2 or not normalized_label:
            raise RuntimeError("US state contract entries must contain a 2-letter code and non-empty label")

        canonical_label = normalized_label.lower()
        if normalized_code in seen_codes:
            raise RuntimeError(f"Duplicate US state code in contract: {normalized_code}")
        if canonical_label in seen_labels:
            raise RuntimeError(f"Duplicate US state label in contract: {normalized_label}")

        seen_codes.add(normalized_code)
        seen_labels.add(canonical_label)
        normalized_entries.append((normalized_code, normalized_label))

    return tuple(normalized_entries)


US_STATE_OPTIONS: Final[tuple[tuple[str, str], ...]] = _load_us_state_contract()
US_STATE_CODES: Final[frozenset[str]] = frozenset(code for code, _ in US_STATE_OPTIONS)
US_STATE_NAME_TO_CODE: Final[dict[str, str]] = {
    label.lower(): code for code, label in US_STATE_OPTIONS
}


def normalize_and_validate_us_state_code(value: str) -> str:
    cleaned = value.strip().upper()
    if cleaned not in US_STATE_CODES:
        raise ValueError("State must be a valid US state code")
    return cleaned
