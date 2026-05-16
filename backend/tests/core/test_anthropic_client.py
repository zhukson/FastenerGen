from app.core.anthropic_client import anthropic_client_options
from app.core.config import settings


def test_anthropic_client_options_include_proxy_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "anthropic_api_key_now", "")
    monkeypatch.setattr(settings, "anthropic_base_url", "http://proxy.test:3000")
    monkeypatch.delenv("ANTHROPIC_API_KEY_NOW", raising=False)

    assert anthropic_client_options() == {
        "api_key": "test-key",
        "base_url": "http://proxy.test:3000",
    }


def test_anthropic_client_options_omit_blank_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "anthropic_api_key_now", "")
    monkeypatch.setattr(settings, "anthropic_base_url", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY_NOW", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    assert anthropic_client_options() == {"api_key": "test-key"}


def test_anthropic_client_options_prefer_proxy_key_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "official-key")
    monkeypatch.setattr(settings, "anthropic_api_key_now", "")
    monkeypatch.setattr(settings, "anthropic_base_url", "http://proxy.test:3000")
    monkeypatch.setenv("ANTHROPIC_API_KEY_NOW", "proxy-key")

    assert anthropic_client_options()["api_key"] == "proxy-key"


def test_anthropic_client_options_read_proxy_key_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "official-key")
    monkeypatch.setattr(settings, "anthropic_api_key_now", "proxy-key")
    monkeypatch.setattr(settings, "anthropic_base_url", "http://proxy.test:3000")
    monkeypatch.delenv("ANTHROPIC_API_KEY_NOW", raising=False)

    assert anthropic_client_options()["api_key"] == "proxy-key"


def test_anthropic_client_options_use_official_key_without_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "settings-official-key")
    monkeypatch.setattr(settings, "anthropic_api_key_now", "proxy-key")
    monkeypatch.setattr(settings, "anthropic_base_url", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "official-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY_NOW", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    assert anthropic_client_options() == {"api_key": "official-key"}
