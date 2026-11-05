import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter conforming to:
    {
        "timestamp": "...",
        "event": "...",
        "module": "...",
        "level": "...",
        "message": "..."
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        # Standard timestamp format ISO 8601 UTC
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        # Extract event name from record attributes or fallback to record funcName / GENERAL
        event_name = getattr(record, "event", None)
        if not event_name:
            event_name = getattr(record, "event_name", "GENERAL")

        log_payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "event": str(event_name),
            "module": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Include exception traceback if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include any additional extra attributes passed by caller
        extra_data = getattr(record, "extra_data", None)
        if isinstance(extra_data, dict):
            log_payload["details"] = extra_data

        return json.dumps(log_payload, default=str)

