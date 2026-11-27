"""Tests for app/config.py."""
import pytest

from app.config import get_settings


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Set safe env vars. load_dotenv() won't override vars that already exist."""
    monkeypatch.setenv("COC_API_KEY", "secret-key-123")
    monkeypatch.setenv("CLAN_TAG", "#TEST")
    monkeypatch.setenv("POLL_MINUTES", "10")
    return monkeypatch


def test_settings_load_from_env(env: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    assert settings.clan_tag == "#TEST"
    assert settings.poll_minutes == 10


def test_repr_hides_api_key(env: pytest.MonkeyPatch) -> None:
    assert "secret-key-123" not in repr(get_settings())


def test_poll_minutes_below_5_is_rejected(env: pytest.MonkeyPatch) -> None:
    env.setenv("POLL_MINUTES", "2")
    with pytest.raises(RuntimeError, match="at least 5"):
        get_settings()
