import logging
import json
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter"""

    def format(self, record):
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log["data"] = record.extra_data
        return json.dumps(log, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging(level: str = "info", fmt: str = "json"):
    """Configure application logging"""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter() if fmt == "json" else TextFormatter())

    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
