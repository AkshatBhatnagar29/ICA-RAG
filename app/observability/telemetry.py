from app.core.logging import configure_logging


def configure_telemetry(log_level: str) -> None:
    configure_logging(log_level)
