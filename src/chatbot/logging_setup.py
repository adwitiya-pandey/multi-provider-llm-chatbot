"""Metadata-only structured JSON audit logging."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

# Strictly allowed metadata keys for audit logs per S5
ALLOWED_LOG_KEYS = {
    "timestamp",
    "level",
    "turn_id",
    "provider",
    "model",
    "retries_used",
    "fallback_used",
    "repair_used",
    "injection_flagged",
    "guardrail_triggered",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "latency_ms",
    "status",
    "error_code",
}

FORBIDDEN_KEY_PATTERNS = {
    "text",
    "prompt",
    "answer",
    "content",
    "reply",
    "key_points",
    "follow_up_questions",
    "api_key",
    "key",
    "secret",
    "token_secret",
}


def filter_metadata(data: dict[str, Any]) -> dict[str, Any]:
    """Filters data dictionary to include ONLY allowed non-sensitive metadata keys."""
    filtered: dict[str, Any] = {}
    for k, v in data.items():
        lower_k = k.lower()
        if lower_k in FORBIDDEN_KEY_PATTERNS:
            continue
        if lower_k in ALLOWED_LOG_KEYS:
            filtered[lower_k] = v
    return filtered


class MetadataJsonFormatter(logging.Formatter):
    """Custom logging formatter outputting clean single-line JSON metadata."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
        }

        # If record has metadata dict passed in args or extra
        metadata: dict[str, Any] = {}
        if hasattr(record, "metadata") and isinstance(record.metadata, dict):
            metadata.update(record.metadata)

        if isinstance(record.args, dict):
            metadata.update(record.args)

        filtered = filter_metadata(metadata)
        payload.update(filtered)

        # Never include raw record.msg if it contains forbidden keys or formatting
        # If record.msg itself looks like status, map it to status
        if record.msg and "status" not in payload and isinstance(record.msg, str):
            if any(forbidden in record.msg.lower() for forbidden in FORBIDDEN_KEY_PATTERNS):
                payload["status"] = "filtered"
            else:
                payload["status"] = record.msg

        return json.dumps(payload, sort_keys=True)


def get_audit_logger(name: str = "chatbot.audit") -> logging.Logger:
    """Configures and returns a dedicated metadata audit logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(MetadataJsonFormatter())
        logger.addHandler(handler)

    return logger


def log_turn_event(logger: logging.Logger, metadata: dict[str, Any]) -> str:
    """Logs a turn event with strict metadata sanitization and returns the JSON string."""
    sanitized = filter_metadata(metadata)
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=sanitized.get("status", "turn_completed"),
        args=(),
        exc_info=None,
    )
    record.metadata = sanitized  # type: ignore[attr-defined]
    formatted = MetadataJsonFormatter().format(record)
    logger.handle(record)
    return formatted
