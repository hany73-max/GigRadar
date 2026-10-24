import pytest
from pydantic_settings import SettingsConfigDict

from gigradar.core.settings import Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Settings, "model_config", SettingsConfigDict(extra="ignore"))
    settings = Settings()
    assert settings.llm_model_scorer == "gemini-2.5-flash"
    assert settings.score_threshold == 65
    assert settings.auto_submit is False
    assert settings.poll_interval_seconds_mostaql == 120
    assert settings.llm_max_rpm == 10
    assert settings.llm_daily_call_budget == 200


def test_settings_env_override(monkeypatch: object) -> None:
    import pytest

    mp = pytest.MonkeyPatch()
    mp.setenv("SCORE_THRESHOLD", "80")
    mp.setenv("AUTO_SUBMIT", "true")
    mp.setenv("LLM_MODEL_SCORER", "gemini-1.5-flash")

    settings = Settings()
    assert settings.score_threshold == 80
    assert settings.auto_submit is True
    assert settings.llm_model_scorer == "gemini-1.5-flash"
    mp.undo()
