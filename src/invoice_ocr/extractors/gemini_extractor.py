from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from invoice_ocr.config import GeminiSettings
from invoice_ocr.models import InvoiceData, InvoiceLineItem, OCRResult

# Prompt instructing Gemini to extract structured fields from raw OCR text
_EXTRACTION_PROMPT = """
You are an invoice data extraction engine for Vietnamese VAT invoices.

Extract all structured fields from the raw OCR text below and return a single JSON object.
Do NOT include any explanation, markdown, or commentary — return raw JSON only.

Required JSON schema:
{{
  "ngay_hd": "YYYY-MM-DD or null",
  "so_hd": "string or null",
  "mst_ncc": "string or null",
  "ten_ncc_raw": "string or null",
  "ma_ncc": null,
  "line_items": [
    {{
      "ten_vt_raw": "string or null",
      "dvt": "string or null",
      "so_luong": number or null,
      "don_gia": number or null,
      "thue_suat_pct": number or null,
      "ma_vt": null,
      "ma_thue": null,
      "tk_kho": null,
      "ma_bp": null,
      "ma_da": null,
      "ghi_chu": null
    }}
  ]
}}

Rules:
- ngay_hd must be normalized to YYYY-MM-DD format.
- so_hd is the invoice number (e.g. 0000087).
- mst_ncc is the supplier tax ID (10 or 13 digits, digits only, no spaces).
- ten_ncc_raw is the supplier name exactly as printed.
- so_luong and don_gia are plain numbers, no thousand separators or units.
- thue_suat_pct is a plain number (e.g. 8, 10, 5, 0) — not a percentage string.
- ma_ncc, ma_vt, ma_thue, tk_kho, ma_bp, ma_da must always be null — do not guess.
- If a field cannot be found, set it to null.

Raw OCR text:
{raw_text}
"""


class GeminiFieldExtractor:
    """
    Field extractor implementation using the Gemini API.

    Implements the FieldExtractor interface.
    Sends raw OCR text to Gemini with a structured prompt and parses
    the JSON response into an InvoiceData object.
    """

    _BASE_URL = "https://generativelanguage.googleapis.com/v1"
    _RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    _MAX_RETRIES = 3
    _INITIAL_BACKOFF_SECONDS = 1.5

    def __init__(self, settings: GeminiSettings) -> None:
        # Unique identifier for this extractor, used for logging and debugging
        self.name = "gemini_extractor"
        self._settings = settings

    def extract_invoice(self, ocr_result: OCRResult) -> InvoiceData:
        """
        Extract structured invoice fields from OCR output.

        Args:
            ocr_result: output from an OCRProvider containing raw_text

        Returns:
            InvoiceData with parsed header fields and line items
        """
        if not ocr_result.raw_text.strip():
            raise ValueError("OCR result contains no text to extract from.")

        prompt = _EXTRACTION_PROMPT.format(raw_text=ocr_result.raw_text)
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }

        response_json = self._generate_content(payload=payload)
        raw_json = self._extract_text_from_response(response_json).strip()
        parsed = self._parse_json(raw_json)

        return self._build_invoice_data(parsed)

    def _build_invoice_data(self, data: dict[str, Any]) -> InvoiceData:
        """Convert parsed JSON dict into a validated InvoiceData object."""
        line_items = [
            InvoiceLineItem(
                ten_vt_raw=item.get("ten_vt_raw"),
                dvt=item.get("dvt"),
                so_luong=item.get("so_luong"),
                don_gia=Decimal(str(item["don_gia"])) if item.get("don_gia") is not None else None,
                thue_suat_pct=item.get("thue_suat_pct"),
                ma_vt=None,
                ma_thue=None,
                tk_kho=None,
                ma_bp=None,
                ma_da=None,
                ghi_chu=item.get("ghi_chu"),
            )
            for item in data.get("line_items", [])
        ]

        ngay_hd_raw = data.get("ngay_hd")
        ngay_hd = date.fromisoformat(ngay_hd_raw) if ngay_hd_raw else None

        return InvoiceData(
            ngay_hd=ngay_hd,
            so_hd=data.get("so_hd"),
            mst_ncc=data.get("mst_ncc"),
            ten_ncc_raw=data.get("ten_ncc_raw"),
            ma_ncc=None,
            line_items=line_items,
        )

    def _parse_json(self, raw_json: str) -> dict[str, Any]:
        """Strip markdown fences if present and parse JSON string."""
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gemini extractor returned invalid JSON: {exc}\nRaw response: {raw_json}"
            ) from exc

    def _generate_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Send request to Gemini API with retry and exponential backoff.

        Retries on transient errors: 429, 500, 502, 503, 504.
        Raises RuntimeError on non-retryable errors or exhausted retries.
        """
        url = f"{self._BASE_URL}/models/{self._settings.model_name}:generateContent"
        params = {"key": self._settings.api_key.get_secret_value()}
        headers = {"Content-Type": "application/json"}

        last_error: Exception | None = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self._settings.timeout_seconds) as client:
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
                        f"Gemini API request failed after {attempt} attempts: {exc}"
                    ) from exc

                self._sleep_before_retry(attempt)

        raise RuntimeError(f"Gemini API request failed: {last_error}")

    def _sleep_before_retry(self, attempt: int) -> None:
        """Exponential backoff before retrying a failed request."""
        import time
        delay_seconds = self._INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
        time.sleep(delay_seconds)

    def _parse_json_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse HTTP response body as JSON, raise on invalid format."""
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("Gemini API returned invalid JSON response.") from exc

    def _extract_text_from_response(self, response_json: dict[str, Any]) -> str:
        """Extract concatenated text from Gemini API response candidates."""
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