from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OCRTextBlock(BaseModel):
    """Represents a single block of text returned by an OCR provider."""

    text: str = Field(..., description="Recognized text content of one OCR block.")
    confidence: float | None = Field(
        default=None,
        description="Confidence score returned by provider, if available.",
    )
    page_number: int = Field(
        default=1,
        ge=1,
        description="1-based page number. For a single image input, default is 1.",
    )
    bbox: list[float] | None = Field(
        default=None,
        description="Bounding box as [x1, y1, x2, y2] if provider returns it.",
    )


class OCRResult(BaseModel):
    """
    Normalized output from any OCR provider.

    Contains the raw extracted text, optional structured blocks,
    and provider-specific metadata. This is the contract between
    the OCRProvider layer and the FieldExtractor layer.
    """

    provider_name: str = Field(..., description="Provider identifier (e.g. 'gemini').")
    raw_text: str = Field(
        default="",
        description="Full flattened OCR text output from the provider.",
    )
    blocks: list[OCRTextBlock] = Field(
        default_factory=list,
        description="Structured OCR blocks if returned by the provider.",
    )
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Provider-specific metadata (e.g. model name, mime type).",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class InvoiceLineItem(BaseModel):
    """
    One product or service line item extracted from an invoice.

    Maps to one row in the staging sheet (Phần B).
    Fields requiring system catalog lookup (ma_vt, ma_thue, tk_kho)
    are nullable — left null if no match is found.
    """

    # Raw fields extracted directly from invoice text
    ten_vt_raw: str | None = Field(
        default=None,
        description="Raw product/service name as printed on the invoice.",
    )
    dvt: str | None = Field(
        default=None,
        description="Unit of measurement as printed (e.g. Kg, Cái, Thùng).",
    )
    so_luong: float | None = Field(
        default=None,
        description="Quantity as a numeric value, no unit suffix.",
    )
    don_gia: Decimal | None = Field(
        default=None,
        description="Unit price excluding VAT, as a precise decimal.",
    )
    thue_suat_pct: float | None = Field(
        default=None,
        description="VAT rate as a plain number (e.g. 8, 10, 5, 0).",
    )

    # Fields requiring system catalog lookup — populated later, not by extractor
    ma_vt: str | None = Field(
        default=None,
        description="Internal material code matched from 12_DM_VAT_TU. Null if not matched.",
    )
    ma_thue: str | None = Field(
        default=None,
        description="Tax code matched from 05_DM_THUE (e.g. GTGT8, GTGT10). Null if not matched.",
    )
    tk_kho: str | None = Field(
        default=None,
        description="Warehouse account code (e.g. 152, 153, 156). Null if not matched.",
    )

    # Optional fields
    ma_bp: str | None = Field(
        default=None,
        description="Department code. Optional, leave null if not applicable.",
    )
    ma_da: str | None = Field(
        default=None,
        description="Project code. Optional, leave null if not applicable.",
    )
    ghi_chu: str | None = Field(
        default=None,
        description="Additional notes for this line item. Optional.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class InvoiceData(BaseModel):
    """
    Fully structured invoice data extracted from OCR output.

    Contains header-level fields (one per invoice) and a list of
    line items (one per product/service row on the invoice).

    This model is the output contract of the FieldExtractor layer.
    Catalog lookup fields (ma_ncc, ma_vt, ma_thue) are nullable —
    they are resolved in a separate mapping/lookup layer downstream.
    """

    # Header fields — appear once per invoice
    ngay_hd: date | None = Field(
        default=None,
        description="Invoice date normalized to a Python date object.",
    )
    so_hd: str | None = Field(
        default=None,
        description="Invoice number as printed on the invoice.",
    )
    mst_ncc: str | None = Field(
        default=None,
        description="Supplier tax ID as printed, 10 or 13 digits.",
    )
    ten_ncc_raw: str | None = Field(
        default=None,
        description="Raw supplier name as printed on the invoice.",
    )

    # Catalog lookup field — populated later, not by extractor
    ma_ncc: str | None = Field(
        default=None,
        description="Internal supplier code matched from 11_DM_DOI_TUONG. Null if not matched.",
    )

    # Line items — one entry per product/service row on the invoice
    line_items: list[InvoiceLineItem] = Field(
        default_factory=list,
        description="List of product/service line items extracted from the invoice.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )