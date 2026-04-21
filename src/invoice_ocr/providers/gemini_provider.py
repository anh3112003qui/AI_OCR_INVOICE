from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from invoice_ocr.config import GeminiSettings
from invoice_ocr.gemini_http_client import GeminiHttpClient
from invoice_ocr.models import OCRResult
from invoice_ocr.types import ImagePath

# Default MIME type used when file extension cannot be detected
_DEFAULT_MIME_TYPE = "image/jpeg"


class GeminiProvider:
    """
    OCR provider adapter for the Gemini Vision API.

    Implements the OCRProvider interface.
    Responsible only for reading an image and returning raw OCR text.
    HTTP communication is delegated to GeminiHttpClient.
    """

    def __init__(self, settings: GeminiSettings) -> None:
        # Unique identifier for this provider, used for logging and OCRResult
        self.name = "gemini"
        self._client = GeminiHttpClient(settings)
        self._model_name = settings.model_name

    def read_image(self, image_path: ImagePath) -> OCRResult:
        """
        Read an invoice image and return normalized OCR output.

        Args:
            image_path: path to the image file (str or Path)

        Returns:
            OCRResult containing raw_text and provider metadata
        """
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Input path is not a file: {path}")

        image_bytes = path.read_bytes()
        if not image_bytes:
            raise ValueError(f"Image file is empty: {path}")

        mime_type = self._resolve_mime_type(path)
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are an OCR engine for invoices. "
                                "Extract all visible text from this image as faithfully as possible. "
                                "Return plain text only. Preserve line breaks where helpful. "
                                "Do not add explanations, markdown, or commentary."
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_b64,
                            }
                        },
                    ]
                }
            ]
        }

        response_json = self._client.generate_content(payload)
        raw_text = self._client.extract_text(response_json).strip()

        return OCRResult(
            provider_name=self.name,
            raw_text=raw_text,
            blocks=[],
            metadata={
                "model_name": self._model_name,
                "mime_type": mime_type,
            },
        )

    def _resolve_mime_type(self, path: Path) -> str:
        """Detect MIME type from file extension, fall back to default."""
        guessed, _ = mimetypes.guess_type(path.name)
        return guessed if guessed else _DEFAULT_MIME_TYPE