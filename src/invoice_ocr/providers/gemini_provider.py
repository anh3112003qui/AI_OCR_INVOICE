from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from invoice_ocr.config import load_gemini_settings
from invoice_ocr.models import OCRResult
from invoice_ocr.types import ImagePath


class GeminiProviderConfig(BaseModel):
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(default="gemini-2.5-flash")
    timeout_seconds: float = Field(default=30.0, gt=0)
    mime_type: str = Field(default="image/jpeg")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class GeminiProvider:
    """
    OCR/vision provider adapter for Gemini API.

    This class is intentionally kept as a skeleton in this step.
    The actual API request/response handling will be implemented later.
    """

    name = "gemini"

    def __init__(self, config: GeminiProviderConfig) -> None:
        self.config = config

    @classmethod
    def from_env(cls, mime_type: str = "image/jpeg") -> "GeminiProvider":
        settings = load_gemini_settings()
        config = GeminiProviderConfig(
            api_key=settings.api_key,
            model_name=settings.model_name,
            timeout_seconds=settings.timeout_seconds,
            mime_type=mime_type,
        )
        return cls(config=config)

    def read_image(self, image_path: ImagePath) -> OCRResult:
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")

        if not path.is_file():
            raise ValueError(f"Input path is not a file: {path}")

        raise NotImplementedError(
            "GeminiProvider.read_image() is not implemented yet. "
            "Next step: add Gemini API request/response logic."
        )