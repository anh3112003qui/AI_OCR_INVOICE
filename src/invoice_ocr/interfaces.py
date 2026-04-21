from __future__ import annotations

from typing import Protocol, runtime_checkable

from invoice_ocr.models import InvoiceData, OCRResult
from invoice_ocr.types import ImagePath
from invoice_ocr.validation import ValidationResult


@runtime_checkable
class OCRProvider(Protocol):
    """
    Contract for any OCR provider (Gemini, Azure, Tesseract, etc.)

    Any class implementing this interface must:
    - Declare instance attribute `name` via __init__
    - Implement `read_image` to return a normalized OCRResult
    """

    def __init__(self, name: str) -> None:
        # Unique identifier for this provider (e.g. "gemini", "azure")
        self.name = name

    def read_image(self, image_path: ImagePath) -> OCRResult:
        """
        Read an invoice image and return normalized OCR output.

        Args:
            image_path: path to the image file (str or Path)

        Returns:
            OCRResult containing raw_text and provider metadata
        """
        ...


@runtime_checkable
class FieldExtractor(Protocol):
    """
    Contract for extracting structured invoice fields from OCR output.

    Any class implementing this interface must:
    - Declare instance attribute `name` via __init__
    - Implement `extract_invoice` to return a normalized InvoiceData
    """

    def __init__(self, name: str) -> None:
        # Unique identifier for this extractor, used for logging and debugging
        self.name = name

    def extract_invoice(self, ocr_result: OCRResult) -> InvoiceData:
        """
        Extract business fields from an OCR result.

        Args:
            ocr_result: output from an OCRProvider containing raw_text

        Returns:
            InvoiceData with parsed and normalized invoice fields
        """
        ...


@runtime_checkable
class Validator(Protocol):
    """
    Contract for validating and normalizing extracted invoice data.

    Any class implementing this interface must:
    - Implement `validate` to return a ValidationResult
    """

    def validate(self, invoice: InvoiceData) -> ValidationResult:
        """
        Validate and normalize an InvoiceData object.

        Args:
            invoice: raw InvoiceData from a FieldExtractor

        Returns:
            ValidationResult containing normalized invoice, errors, and warnings
        """
        ...