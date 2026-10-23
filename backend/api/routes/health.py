from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from api.config import Settings, get_settings
from api.health import CHECKS, HealthReport, run_checks

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthReport,
    responses={503: {"model": HealthReport, "description": "One or more services are down"}},
)
def health(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthReport:
    """Check every external service. 200 if all are ok, 503 otherwise."""
    report = run_checks(CHECKS, settings)
    if report.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
