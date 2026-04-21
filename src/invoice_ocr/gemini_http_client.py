from __future__ import annotations

import time
from typing import Any

import httpx

from invoice_ocr.config import GeminiSettings

_BASE_URL = "https://generativelanguage.googleapis.com/v1"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 1.5


class GeminiHttpClient:
    """
    Low-level HTTP client for the Gemini generateContent API.

    Handles authentication, retry with exponential backoff, and response parsing.
    Not tied to any specific use case (OCR or extraction) — just raw HTTP.

    Used via composition by GeminiProvider and GeminiFieldExtractor.
    """

    def __init__(self, settings: GeminiSettings) -> None:
        self._settings = settings

    def generate_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        POST payload to Gemini generateContent endpoint.

        Retries on transient errors: 429, 500, 502, 503, 504.
        Raises RuntimeError on non-retryable errors or exhausted retries.
        """
        url = f"{_BASE_URL}/models/{self._settings.model_name}:generateContent"
        params = {"key": self._settings.api_key.get_secret_value()}
        headers = {"Content-Type": "application/json"}

        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self._settings.timeout_seconds) as client:
                    response = client.post(url, params=params, headers=headers, json=payload)
                    response.raise_for_status()
                    return self._parse_json_response(response)

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                response_text = exc.response.text.strip()
                last_error = exc

                if status_code not in _RETRYABLE_STATUS_CODES:
                    raise RuntimeError(
                        f"Gemini API returned a non-retryable HTTP error ({status_code}): {response_text}"
                    ) from exc

                if attempt >= _MAX_RETRIES:
                    raise RuntimeError(
                        f"Gemini API returned a retryable HTTP error after {attempt} attempts "
                        f"({status_code}): {response_text}"
                    ) from exc

                self._sleep(attempt)

            except httpx.HTTPError as exc:
                last_error = exc

                if attempt >= _MAX_RETRIES:
                    raise RuntimeError(
                        f"Gemini API request failed after {attempt} attempts: {exc}"
                    ) from exc

                self._sleep(attempt)

        raise RuntimeError(f"Gemini API request failed: {last_error}")

    def extract_text(self, response_json: dict[str, Any]) -> str:
        """Extract concatenated text parts from a Gemini API response dict."""
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
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)

        if not parts:
            raise RuntimeError(
                f"Gemini API response does not contain text parts: {response_json}"
            )

        return "\n".join(parts)

    def _parse_json_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse HTTP response body as JSON, raise on invalid format."""
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("Gemini API returned invalid JSON response.") from exc

    def _sleep(self, attempt: int) -> None:
        """Exponential backoff before retrying a failed request."""
        time.sleep(_INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1)))