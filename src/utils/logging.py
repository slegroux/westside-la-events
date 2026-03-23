"""
Centralized logging configuration.

On Cloud Run (ENVIRONMENT=production), emits JSON lines that Cloud Logging
parses automatically — giving you severity filtering, structured fields,
and proper error grouping in the console.

Locally, uses a human-readable format.
"""
import logging
import json
import os
import sys


class CloudJsonFormatter(logging.Formatter):
    """Format log records as JSON for Google Cloud Logging.

    Cloud Run automatically parses JSON stdout lines and maps the
    ``severity`` field to Cloud Logging severity levels.
    See: https://cloud.google.com/logging/docs/structured-logging
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure the root logger once at startup."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    is_production = os.getenv("ENVIRONMENT") == "production"

    root = logging.getLogger()
    # Avoid adding duplicate handlers on reload
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stderr)
    if is_production:
        handler.setFormatter(CloudJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
        )

    root.setLevel(level)
    root.addHandler(handler)
