"""Each real check must report "not configured" (not crash) when its keys are missing."""

import pytest

from api.config import Settings
from api.health import NotConfiguredError
from api.health_checks import CHECKS

EMPTY = Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("name", [n for n in CHECKS if n != "redis"])
def test_check_reports_not_configured_without_keys(name: str) -> None:
    with pytest.raises(NotConfiguredError):
        CHECKS[name](EMPTY)
