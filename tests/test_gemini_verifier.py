"""Tests for Gemini key verifier and masking utilities."""

from unittest.mock import MagicMock, patch

from gigradar.core.gemini_verifier import is_placeholder, mask_key, verify_gemini_key


def test_is_placeholder() -> None:
    assert is_placeholder(None) is False
    assert is_placeholder("") is False
    assert is_placeholder("real_api_key_123456789") is False
    assert is_placeholder("your_gemini_api_key_here") is True
    assert is_placeholder("your_telegram_token_here") is True
    assert is_placeholder("<your_key>") is True
    assert is_placeholder(123456789) is True
    assert is_placeholder("123456789") is True
    assert is_placeholder(987654321) is False


def test_mask_key() -> None:
    assert mask_key(None) == "<unset>"
    assert mask_key("") == "<unset>"
    assert mask_key("your_gemini_api_key_here") == "<placeholder: your_gem...>"
    assert mask_key("12345") == "***"
    assert mask_key("AIzaSyD1234567890abcdef") == "...cdef"


def test_verify_gemini_key_empty() -> None:
    ok, msg = verify_gemini_key(None)
    assert ok is False
    assert "GEMINI_API_KEY is not set" in msg

    ok2, msg2 = verify_gemini_key("   ")
    assert ok2 is False
    assert "GEMINI_API_KEY is not set" in msg2


def test_verify_gemini_key_placeholder() -> None:
    ok, msg = verify_gemini_key("your_gemini_api_key_here")
    assert ok is False
    assert "Placeholder GEMINI_API_KEY detected" in msg


def test_verify_gemini_key_success() -> None:
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = MagicMock()
        mock_client_cls.return_value = mock_instance

        ok, msg = verify_gemini_key("fake_valid_key", model_id="gemini-3.5-flash-lite")
        assert ok is True
        assert "Live 1-token generation succeeded" in msg
        mock_instance.models.generate_content.assert_called_once_with(
            model="gemini-3.5-flash-lite",
            contents="ping",
            config={"max_output_tokens": 1},
        )


def test_verify_gemini_key_failure() -> None:
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = Exception("Model not found")
        mock_client_cls.return_value = mock_instance

        ok, msg = verify_gemini_key("invalid_key")
        assert ok is False
        assert "Failed 1-token generation" in msg or "rejected key" in msg
