from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from invoice_ocr.models import InvoiceData, InvoiceLineItem
from invoice_ocr.validation import InvoiceValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(**kwargs) -> InvoiceLineItem:
    """Return a valid InvoiceLineItem with defaults, overridden by kwargs."""
    defaults = dict(
        ten_vt_raw="Hat nhua PP",
        dvt="kg",
        so_luong=100.0,
        don_gia=Decimal("38000"),
        thue_suat_pct=8.0,
    )
    defaults.update(kwargs)
    return InvoiceLineItem(**defaults)


def _make_invoice(**kwargs) -> InvoiceData:
    """Return a valid InvoiceData with defaults, overridden by kwargs."""
    defaults = dict(
        ngay_hd=date.today() - timedelta(days=1),
        so_hd="0000087",
        mst_ncc="0310987654",
        ten_ncc_raw="CONG TY TNHH AN PHAT",
        line_items=[_make_item()],
    )
    defaults.update(kwargs)
    return InvoiceData(**defaults)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_invoice_passes() -> None:
    """A fully valid invoice should pass with no errors or warnings."""
    invoice = _make_invoice()
    result = InvoiceValidator().validate(invoice)

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == []


# ---------------------------------------------------------------------------
# MST validation
# ---------------------------------------------------------------------------

def test_mst_10_digits_passes() -> None:
    result = InvoiceValidator().validate(_make_invoice(mst_ncc="0310987654"))
    assert result.is_valid is True


def test_mst_13_digits_passes() -> None:
    result = InvoiceValidator().validate(_make_invoice(mst_ncc="0310987654001"))
    assert result.is_valid is True


def test_mst_missing_warns() -> None:
    result = InvoiceValidator().validate(_make_invoice(mst_ncc=None))
    assert result.is_valid is True
    assert any("mst_ncc" in w for w in result.warnings)


def test_mst_wrong_length_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(mst_ncc="12345"))
    assert result.is_valid is False
    assert any("mst_ncc" in e for e in result.errors)


def test_mst_with_spaces_normalizes() -> None:
    result = InvoiceValidator().validate(_make_invoice(mst_ncc="0 3 1 0 9 8 7 6 5 4"))
    assert result.is_valid is True
    assert result.invoice.mst_ncc == "0310987654"


def test_mst_with_dashes_normalizes() -> None:
    result = InvoiceValidator().validate(_make_invoice(mst_ncc="031-098-7654"))
    assert result.is_valid is True
    assert result.invoice.mst_ncc == "0310987654"


def test_mst_with_letters_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(mst_ncc="031098765X"))
    assert result.is_valid is False
    assert any("mst_ncc" in e for e in result.errors)


# ---------------------------------------------------------------------------
# ngay_hd validation
# ---------------------------------------------------------------------------

def test_ngay_hd_missing_warns() -> None:
    result = InvoiceValidator().validate(_make_invoice(ngay_hd=None))
    assert result.is_valid is True
    assert any("ngay_hd" in w for w in result.warnings)


def test_ngay_hd_today_passes() -> None:
    result = InvoiceValidator().validate(_make_invoice(ngay_hd=date.today()))
    assert result.is_valid is True


def test_ngay_hd_future_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(ngay_hd=date.today() + timedelta(days=1)))
    assert result.is_valid is False
    assert any("future" in e for e in result.errors)


def test_ngay_hd_very_old_warns() -> None:
    result = InvoiceValidator().validate(_make_invoice(ngay_hd=date(2000, 1, 1)))
    assert result.is_valid is True
    assert any("ngay_hd" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# so_hd / ten_ncc_raw
# ---------------------------------------------------------------------------

def test_so_hd_missing_warns() -> None:
    result = InvoiceValidator().validate(_make_invoice(so_hd=None))
    assert result.is_valid is True
    assert any("so_hd" in w for w in result.warnings)


def test_ten_ncc_missing_warns() -> None:
    result = InvoiceValidator().validate(_make_invoice(ten_ncc_raw=None))
    assert result.is_valid is True
    assert any("ten_ncc_raw" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Line item validation
# ---------------------------------------------------------------------------

def test_no_line_items_warns() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[]))
    assert result.is_valid is True
    assert any("line items" in w for w in result.warnings)


def test_so_luong_zero_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(so_luong=0)]))
    assert result.is_valid is False
    assert any("so_luong" in e for e in result.errors)


def test_so_luong_negative_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(so_luong=-1)]))
    assert result.is_valid is False
    assert any("so_luong" in e for e in result.errors)


def test_so_luong_missing_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(so_luong=None)]))
    assert result.is_valid is False
    assert any("so_luong" in e for e in result.errors)


def test_don_gia_zero_passes() -> None:
    """Unit price of 0 is valid (e.g. promotional items)."""
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(don_gia=Decimal("0"))]))
    assert result.is_valid is True


def test_don_gia_negative_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(don_gia=Decimal("-1"))]))
    assert result.is_valid is False
    assert any("don_gia" in e for e in result.errors)


def test_don_gia_missing_errors() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(don_gia=None)]))
    assert result.is_valid is False
    assert any("don_gia" in e for e in result.errors)


# ---------------------------------------------------------------------------
# VAT rate validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rate", [0, 5, 8, 10])
def test_valid_vat_rates_pass(rate: float) -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(thue_suat_pct=rate)]))
    assert result.is_valid is True


@pytest.mark.parametrize("rate", [3, 7, 9, 15, 20])
def test_invalid_vat_rates_error(rate: float) -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(thue_suat_pct=rate)]))
    assert result.is_valid is False
    assert any("thue_suat_pct" in e for e in result.errors)


def test_vat_rate_missing_warns() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(thue_suat_pct=None)]))
    assert result.is_valid is True
    assert any("thue_suat_pct" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_dvt_uppercased() -> None:
    result = InvoiceValidator().validate(_make_invoice(line_items=[_make_item(dvt="kg")]))
    assert result.invoice.line_items[0].dvt == "KG"


def test_so_hd_stripped() -> None:
    result = InvoiceValidator().validate(_make_invoice(so_hd="  0000087  "))
    assert result.invoice.so_hd == "0000087"


def test_ten_ncc_stripped() -> None:
    result = InvoiceValidator().validate(_make_invoice(ten_ncc_raw="  AN PHAT  "))
    assert result.invoice.ten_ncc_raw == "AN PHAT"


# ---------------------------------------------------------------------------
# Multiple errors accumulate
# ---------------------------------------------------------------------------

def test_multiple_errors_accumulate() -> None:
    """Validator must not stop at first error — collect all issues."""
    bad_items = [
        _make_item(so_luong=-1, don_gia=Decimal("-500"), thue_suat_pct=7),
    ]
    invoice = _make_invoice(
        mst_ncc="INVALID",
        ngay_hd=date.today() + timedelta(days=5),
        line_items=bad_items,
    )
    result = InvoiceValidator().validate(invoice)

    assert result.is_valid is False
    assert len(result.errors) >= 4  # mst, ngay_hd, so_luong, don_gia, thue_suat


if __name__ == "__main__":
    import pytest as pt
    pt.main([__file__, "-v"])