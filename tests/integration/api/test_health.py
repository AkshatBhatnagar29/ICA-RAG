from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_health_is_independent_of_dependencies() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_ready_reports_success() -> None:
    with patch("app.api.v1.endpoints.health.check_readiness", new_callable=AsyncMock) as check:
        check.return_value = {"postgres": "ok", "redis": "ok"}
        with TestClient(app) as client:
            response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


def test_ready_reports_dependency_failure() -> None:
    from app.core.exceptions import DependencyUnavailableError

    with patch(
        "app.api.v1.endpoints.health.check_readiness",
        new_callable=AsyncMock,
        side_effect=DependencyUnavailableError("redis"),
    ), TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"redis": "unavailable"}}


def test_unexpected_errors_are_safe() -> None:
    with patch(
        "app.api.v1.endpoints.health.check_readiness",
        new_callable=AsyncMock,
        side_effect=RuntimeError("secret details"),
    ), TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 500
    assert "secret details" not in response.text
    assert response.json()["error"]["code"] == "internal_error"
