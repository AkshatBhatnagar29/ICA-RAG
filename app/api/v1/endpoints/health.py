from fastapi import APIRouter, Request, Response, status

from app.core.exceptions import DependencyUnavailableError
from app.observability.metrics import metrics
from app.services.health import check_readiness

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
async def application_metrics() -> dict[str, object]:
    return metrics.snapshot()


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict[str, object]:
    try:
        checks = await check_readiness(request.app.state.resources, request.app.state.settings)
    except DependencyUnavailableError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": {exc.dependency: "unavailable"}}
    return {"status": "ok", "checks": checks}
