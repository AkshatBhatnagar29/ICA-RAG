import logging
import re
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_context
from app.observability.metrics import metrics

logger = logging.getLogger(__name__)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_request_id = next(
            (value for key, value in scope.get("headers", []) if key == b"x-request-id"),
            str(uuid4()),
        )
        candidate = raw_request_id.decode("ascii", errors="ignore") if isinstance(raw_request_id, bytes) else raw_request_id
        request_id = candidate if _REQUEST_ID.fullmatch(candidate) else str(uuid4())
        scope["state"] = {**scope.get("state", {}), "request_id": request_id}
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                nonlocal status_code
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                existing = {key.lower() for key, _ in headers}
                for key, value in ((b"x-content-type-options", b"nosniff"),
                                   (b"x-frame-options", b"DENY"),
                                   (b"referrer-policy", b"no-referrer")):
                    if key not in existing:
                        headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            route = scope.get("path", "unknown")
            metrics.increment("http_requests_total", endpoint=route, method=scope.get("method", ""), status=status_code)
            if status_code >= 400:
                metrics.increment("http_request_failures_total", endpoint=route, status=status_code)
            metrics.observe("http_request_latency_ms", duration_ms, endpoint=route, method=scope.get("method", ""))
            logger.info("http_request_completed", extra={"endpoint": route, "method": scope.get("method", ""),
                                                          "status_code": status_code, "duration_ms": round(duration_ms, 3)})
            request_id_context.reset(token)
