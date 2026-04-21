from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from invoice_ocr.config import GeminiSettings
from invoice_ocr.exporters.excel_exporter import ExcelExporter
from invoice_ocr.extractors.gemini_extractor import GeminiFieldExtractor
from invoice_ocr.providers.gemini_provider import GeminiProvider
from invoice_ocr.types import ImagePath
from invoice_ocr.validation import InvoiceValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """
    Result of running the full OCR invoice pipeline for one image.

    Attributes:
        image_path: input image that was processed
        validation: full ValidationResult including normalized InvoiceData
        rows_written: number of rows appended to the Excel sheet (0 on error)
        error: exception message if pipeline failed before writing, else None
    """

    image_path: Path
    validation: ValidationResult | None
    rows_written: int
    error: str | None

    @property
    def success(self) -> bool:
        """True if pipeline completed without an unhandled exception."""
        return self.error is None


class InvoicePipeline:
    """
    Orchestrates the full invoice processing pipeline:
      image → OCR → field extraction → validation → Excel export

    All layers are injected via __init__ for testability and provider flexibility.
    """

    def __init__(
        self,
        provider: GeminiProvider,
        extractor: GeminiFieldExtractor,
        validator: InvoiceValidator,
        exporter: ExcelExporter,
    ) -> None:
        self._provider = provider
        self._extractor = extractor
        self._validator = validator
        self._exporter = exporter

    def run(self, image_path: ImagePath) -> PipelineResult:
        """
        Process one invoice image end-to-end.

        Args:
            image_path: path to the invoice image file

        Returns:
            PipelineResult with validation output and rows written
        """
        path = Path(image_path)
        logger.info("Pipeline started: %s", path.name)

        try:
            # Step 1: OCR
            logger.info("[1/4] OCR: reading image")
            ocr_result = self._provider.read_image(path)
            logger.info("[1/4] OCR: extracted %d chars", len(ocr_result.raw_text))

            # Step 2: Field extraction
            logger.info("[2/4] Extraction: parsing fields")
            invoice_data = self._extractor.extract_invoice(ocr_result)
            logger.info(
                "[2/4] Extraction: so_hd=%s, %d line items",
                invoice_data.so_hd,
                len(invoice_data.line_items),
            )

            # Step 3: Validation + normalization
            logger.info("[3/4] Validation: checking invoice data")
            validation = self._validator.validate(invoice_data)

            if validation.errors:
                logger.warning(
                    "[3/4] Validation: %d error(s) — will still write to sheet",
                    len(validation.errors),
                )
                for err in validation.errors:
                    logger.warning("  ERROR: %s", err)

            if validation.warnings:
                for warn in validation.warnings:
                    logger.info("  WARN: %s", warn)

            # Step 4: Export to Excel
            logger.info("[4/4] Export: appending to staging sheet")
            rows_written = self._exporter.append(validation)
            logger.info("[4/4] Export: wrote %d rows", rows_written)

            return PipelineResult(
                image_path=path,
                validation=validation,
                rows_written=rows_written,
                error=None,
            )

        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", path.name, exc, exc_info=True)
            return PipelineResult(
                image_path=path,
                validation=None,
                rows_written=0,
                error=str(exc),
            )


def build_pipeline(workbook_path: str | Path) -> InvoicePipeline:
    """
    Convenience factory: build a fully wired InvoicePipeline from settings and workbook path.

    Loads GeminiSettings from environment / .env / settings.yaml automatically.

    Args:
        workbook_path: path to the Excel workbook containing the staging sheet

    Returns:
        InvoicePipeline ready to call .run(image_path)
    """
    settings = GeminiSettings()
    return InvoicePipeline(
        provider=GeminiProvider(settings=settings),
        extractor=GeminiFieldExtractor(settings=settings),
        validator=InvoiceValidator(),
        exporter=ExcelExporter(workbook_path=workbook_path),
    )