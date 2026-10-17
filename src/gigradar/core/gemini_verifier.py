"""Verification utility for Google Gemini API key and model connectivity."""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def mask_key(key: str | None) -> str:
    """Safely mask an API key for logs and terminal display."""
    if not key:
        return "<unset>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def verify_gemini_key(api_key: str | None, model_id: str = "gemini-2.5-flash") -> tuple[bool, str]:
    """Verify Gemini API key validity and connectivity using the official google-genai SDK.

    Returns:
        (is_valid, details_message)
    """
    if not api_key or not api_key.strip():
        return False, "GEMINI_API_KEY is not set. Please provide it in your .env file or environment."

    clean_key = api_key.strip()

    try:
        from google import genai
        from google.genai import errors

        client = genai.Client(api_key=clean_key)
        # Verify by fetching model metadata
        model_info: Any = client.models.get(model=model_id)
        display_name = getattr(model_info, "display_name", model_id)
        return True, f"Key verified successfully. Reached model '{model_id}' ({display_name})."

    except ImportError:
        return False, "The 'google-genai' SDK is not installed."
    except errors.ClientError as exc:
        # Extract friendly message without exposing the key
        msg = getattr(exc, "message", str(exc))
        return False, f"Google API rejected key [{mask_key(clean_key)}]: {msg}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Failed to connect to Gemini API: {exc}"
