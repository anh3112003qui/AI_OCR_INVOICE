from __future__ import annotations

import re
from datetime import date, timedelta

from pydantic import BaseModel

from invoice_ocr.models import InvoiceData, InvoiceLineItem

# Valid VAT rates under Vietnamese tax law (Luat Thue GTGT 2024 + ND 174/2025)
# 0%, 5%: permanent rates
# 8%: reduced from 10%, applies 01/07/2025 - 31/12/2026 per ND 174/2025
# 10%: standard rate
_VALID_VAT_RATES = {0, 5, 8, 10}

# MST must be exactly 10 or 13 digits (ND 123/2020)
_MST_PATTERN = re.compile(r"^\d{10}$|^\d{13}$")

# Invoice date must not be in the future, and not older than 10 years
_MAX_INVOICE_AGE_DAYS = 3650


class ValidationResult(BaseModel):
    """
    Result of validating and normalizing an InvoiceData object.

    - errors: blocking issues, data is likely incorrect
    - warnings: non-blocking issues, data may still be usable
    - invoice: the normalized InvoiceData (fields cleaned even if errors exist)
    """

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    invoice: InvoiceData


class InvoiceValidator:
    """
    Validates and normalizes an InvoiceData object against Vietnamese VAT invoice rules.

    Does not raise exceptions — always returns a ValidationResult so the caller
    can decide how to handle errors (log, flag for review, reject, etc.).
    """

    def validate(self, invoice: InvoiceData) -> ValidationResult:
        """
        Validate and normalize invoice data.

        Args:
            invoice: raw InvoiceData from FieldExtractor

        Returns:
            ValidationResult with normalized invoice, errors, and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        normalized = self._normalize(invoice)
        self._validate_header(normalized, errors, warnings)
        self._validate_line_items(normalized, errors, warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            invoice=normalized,
        )

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, invoice: InvoiceData) -> InvoiceData:
        """Return a new InvoiceData with cleaned field values."""
        return InvoiceData(
            ngay_hd=invoice.ngay_hd,
            so_hd=invoice.so_hd.strip() if invoice.so_hd else None,
            mst_ncc=self._normalize_mst(invoice.mst_ncc),
            ten_ncc_raw=invoice.ten_ncc_raw.strip() if invoice.ten_ncc_raw else None,
            ma_ncc=invoice.ma_ncc,
            line_items=[self._normalize_line_item(item) for item in invoice.line_items],
        )

    def _normalize_mst(self, mst: str | None) -> str | None:
        """Strip spaces, dashes, and dots from MST string."""
        if mst is None:
            return None
        return re.sub(r"[\s\-.]", "", mst)

    def _normalize_line_item(self, item: InvoiceLineItem) -> InvoiceLineItem:
        """Return a new InvoiceLineItem with cleaned field values."""
        return InvoiceLineItem(
            ten_vt_raw=item.ten_vt_raw.strip() if item.ten_vt_raw else None,
            dvt=item.dvt.strip().upper() if item.dvt else None,
            so_luong=item.so_luong,
            don_gia=item.don_gia,
            thue_suat_pct=item.thue_suat_pct,
            ma_vt=item.ma_vt,
            ma_thue=item.ma_thue,
            tk_kho=item.tk_kho,
            ma_bp=item.ma_bp,
            ma_da=item.ma_da,
            ghi_chu=item.ghi_chu.strip() if item.ghi_chu else None,
        )

    # ------------------------------------------------------------------
    # Header validation
    # ------------------------------------------------------------------

    def _validate_header(
        self,
        invoice: InvoiceData,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        self._validate_mst(invoice.mst_ncc, errors, warnings)
        self._validate_ngay_hd(invoice.ngay_hd, errors, warnings)
        self._validate_so_hd(invoice.so_hd, warnings)
        self._validate_ten_ncc(invoice.ten_ncc_raw, warnings)

    def _validate_mst(
        self,
        mst: str | None,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if mst is None:
            warnings.append("mst_ncc is missing.")
            return
        if not _MST_PATTERN.match(mst):
            errors.append(
                f"mst_ncc '{mst}' is invalid — must be exactly 10 or 13 digits."
            )

    def _validate_ngay_hd(
        self,
        ngay_hd: date | None,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if ngay_hd is None:
            warnings.append("ngay_hd is missing.")
            return

        today = date.today()

        if ngay_hd > today:
            errors.append(
                f"ngay_hd '{ngay_hd}' is in the future."
            )
        elif ngay_hd < today - timedelta(days=_MAX_INVOICE_AGE_DAYS):
            warnings.append(
                f"ngay_hd '{ngay_hd}' is more than 10 years ago — please verify."
            )

    def _validate_so_hd(self, so_hd: str | None, warnings: list[str]) -> None:
        if not so_hd:
            warnings.append("so_hd is missing.")

    def _validate_ten_ncc(self, ten_ncc: str | None, warnings: list[str]) -> None:
        if not ten_ncc:
            warnings.append("ten_ncc_raw is missing.")

    # ------------------------------------------------------------------
    # Line item validation
    # ------------------------------------------------------------------

    def _validate_line_items(
        self,
        invoice: InvoiceData,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if not invoice.line_items:
            warnings.append("Invoice has no line items.")
            return

        for i, item in enumerate(invoice.line_items):
            prefix = f"Line item {i + 1}"
            self._validate_item_name(item.ten_vt_raw, prefix, warnings)
            self._validate_so_luong(item.so_luong, prefix, errors)
            self._validate_don_gia(item.don_gia, prefix, errors)
            self._validate_thue_suat(item.thue_suat_pct, prefix, errors, warnings)

    def _validate_item_name(
        self,
        ten_vt_raw: str | None,
        prefix: str,
        warnings: list[str],
    ) -> None:
        if not ten_vt_raw:
            warnings.append(f"{prefix}: ten_vt_raw is missing.")

    def _validate_so_luong(
        self,
        so_luong: float | None,
        prefix: str,
        errors: list[str],
    ) -> None:
        if so_luong is None:
            errors.append(f"{prefix}: so_luong is missing.")
        elif so_luong <= 0:
            errors.append(f"{prefix}: so_luong must be > 0, got {so_luong}.")

    def _validate_don_gia(
        self,
        don_gia: object,
        prefix: str,
        errors: list[str],
    ) -> None:
        if don_gia is None:
            errors.append(f"{prefix}: don_gia is missing.")
        elif don_gia < 0:
            errors.append(f"{prefix}: don_gia must be >= 0, got {don_gia}.")

    def _validate_thue_suat(
        self,
        thue_suat_pct: float | None,
        prefix: str,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if thue_suat_pct is None:
            warnings.append(f"{prefix}: thue_suat_pct is missing.")
            return
        if thue_suat_pct not in _VALID_VAT_RATES:
            errors.append(
                f"{prefix}: thue_suat_pct {thue_suat_pct} is not a valid VAT rate "
                f"(valid: {sorted(_VALID_VAT_RATES)})."
            )