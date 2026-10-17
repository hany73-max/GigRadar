"""Utility script to test live structured outputs with Gemini API."""

import sys

from pydantic import BaseModel, Field

from gigradar.core.gemini_verifier import mask_key
from gigradar.core.settings import get_settings


class EchoCheck(BaseModel):
    status: str = Field(description="Must be 'success'")
    reply: str = Field(description="Short confirmation message")


def main() -> int:
    settings = get_settings()
    key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""

    if not key or key in ("your_gemini_api_key_here", "<unset>"):
        print(
            f"[SKIP] No real GEMINI_API_KEY set (current: {mask_key(key)}). Skipping live API call."
        )
        return 0

    print(
        f"[INFO] Real key found ({mask_key(key)}). Testing structured output on model: {settings.llm_model_scorer}..."
    )
    try:
        from google import genai

        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=settings.llm_model_scorer,
            contents="Respond with status 'success' and reply 'Structured output functional'.",
            config={
                "response_mime_type": "application/json",
                "response_schema": EchoCheck,
            },
        )
        parsed = response.parsed
        print(f"[PASS] Structured output succeeded! Parsed response: {parsed}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Structured output call failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
