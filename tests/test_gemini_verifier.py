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
    assert mask_key("AIzaSyD1234567890abcdef") == "AIza...cdef"


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
        mock_model = MagicMock()
        mock_model.display_name = "Gemini 2.5 Flash"
        mock_instance.models.get.return_value = mock_model
        mock_client_cls.return_value = mock_instance

        ok, msg = verify_gemini_key("fake_valid_key", model_id="gemini-2.5-flash")
        assert ok is True
        assert "Key verified successfully" in msg
        mock_instance.models.get.assert_called_once_with(model="gemini-2.5-flash")


def test_verify_gemini_key_failure() -> None:
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.get.side_effect = Exception("API Key not found")
        mock_client_cls.return_value = mock_instance

        ok, msg = verify_gemini_key("invalid_key")
        assert ok is False
        assert "Failed to connect" in msg or "rejected key" in msg
