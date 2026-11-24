"""Regression tests for the notarial amount validator.

Only fictitious values are used. Amounts are a financial precision boundary:
no binary float, no silent rounding to grosz, no NaN or Infinity.
"""
import pytest

from walidacja import kwota, sprawdz_pole


@pytest.mark.parametrize(("raw", "expected"), [
    ("0", "0.00"),
    ("10", "10.00"),
    ("1234.56", "1234.56"),
    ("1234,56", "1234.56"),
    ("1 234,56", "1234.56"),
    ("1\u00a0234.56", "1234.56"),
    ("1\u202f234,56", "1234.56"),
    ("1234.56 PLN", "1234.56"),
    ("1234.56 zl", "1234.56"),
    ("1 234,56 zł", "1234.56"),
    ("0,01", "0.01"),
    ("+123.45", "123.45"),
    ("999999999999999999,99", "999999999999999999.99"),
    ("0.10", "0.10"),
    ("0.29", "0.29"),
    ("999999999999.99", "999999999999.99"),
])
def test_exact_acceptable_amounts(raw, expected):
    ok, message = kwota(raw)
    assert ok is True
    assert message == expected + " zl"


@pytest.mark.parametrize("raw", [
    "NaN", "nan", "nan zl", "inf", "-inf", "Infinity", "+Infinity",
    "1e309", "1E3", "1.234,56", "1,234.56", "12.345", "0,001",
    "1,2,3", "1.00.00", "1,2 EUR", "1000000000000000000",
    "１２３４", "1_000", "", None, "abc", "-0", " -1 ", "-100", "--10",
    "123złzł", "0x10", "1/2", "1\u0000", "1234.00 USD",
])
def test_reject_ambiguous_or_unsafe_amount(raw):
    ok, _ = kwota(raw)
    assert ok is False


@pytest.mark.parametrize("raw", ["-100", "-1,25", "-0"])
def test_negative_amounts_reported_as_negative(raw):
    ok, message = kwota(raw)
    assert ok is False
    assert "ujemna" in message.lower()


def test_no_binary_float_rounding():
    ok, message = kwota("100000000000000001,99")
    assert ok and message == "100000000000000001.99 zl"


def test_field_dispatcher_rejects_not_a_number():
    for field in ("kwota pożyczki", "cena nabycia", "wartość nieruchomości"):
        ok, _ = sprawdz_pole(field, "NaN")
        assert ok is False
