from decimal import Decimal

import pytest

from api.config import Settings


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ORG", "my-agents")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.github_org == "my-agents"


def test_missing_values_default_to_none() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.openrouter_api_key is None


def test_money_settings_are_exact_decimals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USD_TO_INR", "97.25")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.usd_to_inr == Decimal("97.25")
    assert settings.story_budget_inr == Decimal("50")


def test_secrets_are_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-very-secret")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert "sk-or-very-secret" not in repr(settings)
    assert "sk-or-very-secret" not in str(settings.openrouter_api_key)
    # The real value is only reachable on purpose:
    assert settings.openrouter_api_key is not None
    assert settings.openrouter_api_key.get_secret_value() == "sk-or-very-secret"
