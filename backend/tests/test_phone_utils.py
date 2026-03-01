import pytest

from app.utils.phone import normalize_phone_number


@pytest.mark.unit
def test_normalize_phone_number_adds_us_country_code_for_10_digits():
    assert normalize_phone_number("3054959490") == "+13054959490"
    assert normalize_phone_number("(305) 495-9490") == "+13054959490"


@pytest.mark.unit
def test_normalize_phone_number_handles_existing_plus_country_code():
    assert normalize_phone_number("+1 (305) 495-9490") == "+13054959490"
    assert normalize_phone_number("+44 20 7946 0958") == "+442079460958"


@pytest.mark.unit
def test_normalize_phone_number_preserves_non_numeric_legacy_tokens():
    assert normalize_phone_number("555-CA-1001") == "555-CA-1001"


@pytest.mark.unit
def test_normalize_phone_number_returns_none_for_blank_input():
    assert normalize_phone_number(None) is None
    assert normalize_phone_number("   ") is None
