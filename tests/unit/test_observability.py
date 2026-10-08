import json
import logging
import uuid

from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter
from app.main import app
from app.observability.metrics import metrics


def test_request_id_is_propagated_and_invalid_ids_are_replaced() -> None:
    supplied = "smoke-test-123"
    with TestClient(app) as client:
        response = client.get("/api/v1/health", headers={"X-Request-ID": supplied})
        invalid = client.get("/api/v1/health", headers={"X-Request-ID": "x" * 129})

    assert response.headers["x-request-id"] == supplied
    generated = invalid.headers["x-request-id"]
    uuid.UUID(generated)


def test_structured_formatter_redacts_secrets_and_omits_sensitive_fields() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1,
                               "Authorization: Bearer abc123 api_key=secret", (), None)
    record.request_id = "request-1"
    record.tenant_id = "sensitive-tenant"
    record.category = "authentication_error"

    output = json.loads(JsonFormatter().format(record))
    assert output["message"] == "Authorization: Bearer [REDACTED] api_key=[REDACTED]"
    assert "tenant_id" not in output
    assert output["category"] == "authentication_error"


def test_metrics_are_available_through_internal_endpoint() -> None:
    metrics.increment("test_observability_counter")
    with TestClient(app) as client:
        response = client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert response.json()["counters"]["test_observability_counter"] >= 1
