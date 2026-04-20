from __future__ import annotations

from typing import Protocol

from invoice_ocr.models import InvoiceData, OCRResult
from invoice_ocr.types import ImagePath


class OCRProvider(Protocol):
    """Read invoice image and return normalized OCR output."""

    name: str

    def read_image(self, image_path: ImagePath) -> OCRResult:
        """Read a single image and return normalized OCR result."""
        ...


class FieldExtractor(Protocol):
    """Extract structured invoice fields from OCR result."""

    name: str

    def extract_invoice(self, ocr_result: OCRResult) -> InvoiceData:
        """Convert OCR result into normalized invoice data."""
        ...