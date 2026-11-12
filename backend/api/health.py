"""Health checks: one small function per external service.

A check function takes the settings and either returns (healthy) or raises.
- NotConfiguredError: the service's keys are not in .env yet.
- Any other exception: the service is configured but unreachable or broken.

The real checks and their registry live in api/health_checks.py.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Literal

from pydantic import BaseModel

from api.config import Settings

CHECK_TIMEOUT_SECONDS = 5.0
MAX_DETAIL_LENGTH = 200


class NotConfiguredError(Exception):
    """Raised by a check when the service has no keys in .env yet."""


CheckFn = Callable[[Settings], None]


class ServiceStatus(BaseModel):
    status: Literal["ok", "error", "not_configured"]
    detail: str | None = None


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    services: dict[str, ServiceStatus]


def _describe(exc: BaseException) -> str:
    # Short and generic: error type plus a trimmed message. Never the settings.
    return f"{type(exc).__name__}: {exc}"[:MAX_DETAIL_LENGTH]


def run_checks(
    checks: dict[str, CheckFn], settings: Settings, optional: frozenset[str] = frozenset()
) -> HealthReport:
    """Run every check in parallel so one slow service can't stall the others.
    optional: services we can run without. One of these with no keys set is reported
    as not_configured but doesn't make the report degraded; a broken one still does."""
    services: dict[str, ServiceStatus] = {}
    if checks:
        with ThreadPoolExecutor(max_workers=len(checks)) as pool:
            futures = {name: pool.submit(check, settings) for name, check in checks.items()}
            for name, future in futures.items():
                try:
                    future.result(timeout=CHECK_TIMEOUT_SECONDS)
                    services[name] = ServiceStatus(status="ok")
                except NotConfiguredError as exc:
                    services[name] = ServiceStatus(status="not_configured", detail=str(exc))
                except FutureTimeoutError:
                    services[name] = ServiceStatus(status="error", detail="Timed out")
                except Exception as exc:  # any failure means "error", never a crash
                    services[name] = ServiceStatus(status="error", detail=_describe(exc))

    all_ok = all(
        s.status == "ok" or (s.status == "not_configured" and name in optional)
        for name, s in services.items()
    )
    return HealthReport(status="ok" if all_ok else "degraded", services=services)
