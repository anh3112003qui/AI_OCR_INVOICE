from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OCRTextBlock(BaseModel):
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
    provider_name: str = Field(..., description="Provider identifier.")
    raw_text: str = Field(
        default="",
        description="Flattened OCR text output.",
    )
    blocks: list[OCRTextBlock] = Field(
        default_factory=list,
        description="Structured OCR blocks if available.",
    )
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Provider-specific metadata.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class InvoiceData(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: str | None = None
    currency: str | None = None

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )