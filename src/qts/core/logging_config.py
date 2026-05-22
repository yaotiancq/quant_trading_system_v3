"""Logging setup for command-line and runtime entry points."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """Minimal structured formatter without external dependencies."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


def configure_logging(
    *,
    level: str | int = "INFO",
    structured: bool = False,
    log_file: str | Path | None = None,
) -> logging.Logger:
    """Configure root logging once and return the project logger."""
    numeric_level = logging.getLevelName(level.upper()) if isinstance(level, str) else level
    if not isinstance(numeric_level, int):
        raise ValueError(f"invalid log level: {level!r}")

    formatter: logging.Formatter
    if structured:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        formatter.converter = time_gmt  # type: ignore[method-assign]

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(numeric_level)
    for handler in handlers:
        handler.setLevel(numeric_level)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    return logging.getLogger("qts")


def time_gmt(*args: Any) -> Any:
    return __import__("time").gmtime(*args)


__all__ = ["JsonFormatter", "configure_logging"]
