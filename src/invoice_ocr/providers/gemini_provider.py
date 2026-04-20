from __future__ import annotations

import base64
import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from invoice_ocr.config import load_gemini_settings
from invoice_ocr.models import OCRResult
from invoice_ocr.types import ImagePath


class GeminiProviderConfig(BaseModel):
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(default="gemini-2.5-flash-lite")
    timeout_seconds: float = Field(default=30.0, gt=0)
    mime_type: str = Field(default="image/jpeg")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class GeminiProvider:
    """
    OCR/vision provider adapter for Gemini API.
    """

    name = "gemini"
    _BASE_URL = "https://generativelanguage.googleapis.com/v1"
    _RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    _MAX_RETRIES = 3
    _INITIAL_BACKOFF_SECONDS = 1.5

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

        response_json = self._generate_content(payload=payload)
        raw_text = self._extract_text_from_response(response_json).strip()

        return OCRResult(
            provider_name=self.name,
            raw_text=raw_text,
            blocks=[],
            metadata={
                "model_name": self.config.model_name,
                "mime_type": mime_type,
            },
        )

    def _resolve_mime_type(self, path: Path) -> str:
        guessed_mime_type, _ = mimetypes.guess_type(path.name)
        if guessed_mime_type:
            return guessed_mime_type
        return self.config.mime_type

    def _generate_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = (
            f"{self._BASE_URL}/models/"
            f"{self.config.model_name}:generateContent"
        )
        params = {"key": self.config.api_key}
        headers = {"Content-Type": "application/json"}

        last_error: Exception | None = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self.config.timeout_seconds) as client:
                    response = client.post(
                        url,
                        params=params,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    return self._parse_json_response(response)

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                response_text = exc.response.text.strip()
                last_error = exc

                if status_code not in self._RETRYABLE_STATUS_CODES:
                    raise RuntimeError(
                        "Gemini API returned a non-retryable HTTP error "
                        f"({status_code}): {response_text}"
                    ) from exc

                if attempt >= self._MAX_RETRIES:
                    raise RuntimeError(
                        "Gemini API returned a retryable HTTP error after "
                        f"{attempt} attempts ({status_code}): {response_text}"
                    ) from exc

                self._sleep_before_retry(attempt)

            except httpx.HTTPError as exc:
                last_error = exc

                if attempt >= self._MAX_RETRIES:
                    raise RuntimeError(
                        "Gemini API request failed after "
                        f"{attempt} attempts: {exc}"
                    ) from exc

                self._sleep_before_retry(attempt)

        raise RuntimeError(f"Gemini API request failed: {last_error}")

    def _sleep_before_retry(self, attempt: int) -> None:
        delay_seconds = self._INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
        time.sleep(delay_seconds)

    def _parse_json_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("Gemini API returned invalid JSON response.") from exc

    def _extract_text_from_response(self, response_json: dict[str, Any]) -> str:
        candidates = response_json.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError(
                f"Gemini API response does not contain candidates: {response_json}"
            )

        parts: list[str] = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            content = candidate.get("content")
            if not isinstance(content, dict):
                continue

            content_parts = content.get("parts")
            if not isinstance(content_parts, list):
                continue

            for part in content_parts:
                if not isinstance(part, dict):
                    continue

                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text)

        if not parts:
            raise RuntimeError(
                f"Gemini API response does not contain text parts: {response_json}"
            )

        return "\n".join(parts)