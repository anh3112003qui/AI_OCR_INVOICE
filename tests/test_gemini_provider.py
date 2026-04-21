from __future__ import annotations

from pathlib import Path

from invoice_ocr.config import GeminiSettings
from invoice_ocr.providers import GeminiProvider

# Path to sample invoice image for manual smoke test
_INVOICE_PATH = Path(__file__).resolve().parent.parent / "data" / "invoice.png"


def test_gemini_provider_read_image() -> None:
    """Smoke test: verify GeminiProvider can read a real invoice image."""
    settings = GeminiSettings()
    provider = GeminiProvider(settings=settings)

    result = provider.read_image(_INVOICE_PATH)

    print("\n--- raw_text ---")
    print(result.raw_text)
    print("\n--- model_dump ---")
    print(result.model_dump())

    assert result.provider_name == "gemini"
    assert isinstance(result.raw_text, str)
    assert len(result.raw_text) > 0


if __name__ == "__main__":
    test_gemini_provider_read_image()
    print("\nOK")