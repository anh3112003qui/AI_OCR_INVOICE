from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field


class GeminiSettings(BaseModel):
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(default="gemini-2.5-flash-lite")
    timeout_seconds: float = Field(default=30.0, gt=0)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


def load_gemini_settings() -> GeminiSettings:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite").strip()
    timeout_raw = os.getenv("GEMINI_TIMEOUT_SECONDS", "30").strip()

    if not api_key:
        raise ValueError("Missing required environment variable: GEMINI_API_KEY")

    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ValueError(
            "Environment variable GEMINI_TIMEOUT_SECONDS must be a valid number."
        ) from exc

    return GeminiSettings(
        api_key=api_key,
        model_name=model_name,
        timeout_seconds=timeout_seconds,
    )