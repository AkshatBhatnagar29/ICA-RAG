import json
import logging
import re
import sys
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
_SECRET = re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?|bearer\s+|(?:api[_-]?key|password|jwt[_-]?secret)\s*[:=]\s*)[^\s,;]+")
_SAFE_FIELDS = {"endpoint", "method", "status_code", "duration_ms", "category", "provider",
                "retrieved_count", "generation_selected_count", "generation_context_token_estimate",
                "provider_request_size", "candidate_evidence_count", "selected_evidence_count",
                "evidence_ids_sent_to_llm"}


class JsonFormatter(logging.Formatter):
    """Small, dependency-free JSON formatter for operational, content-free logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": _SECRET.sub(r"\1[REDACTED]", record.getMessage()),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {"message", "asctime", "request_id"}:
                continue
            if key in {"args", " exc_info", "exc_text", "stack_info", "msg"}:
                continue
            if key in _SAFE_FIELDS and (isinstance(value, (str, int, float, bool, type(None)))
                                        or (key == "evidence_ids_sent_to_llm" and
                                            isinstance(value, list) and all(isinstance(item, str) for item in value))):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(
        level=level.upper(),
        handlers=[handler],
        force=True,
    )


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_context.get()
        return True
