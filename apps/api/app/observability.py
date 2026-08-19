"""Secret-safe structured logging for redacted unexpected failures."""

from __future__ import annotations

import json
import logging


_LOGGER = logging.getLogger("zimo.api")
_OPERATIONS = frozenset(
    {
        "http.authentication",
        "http.exception",
        "http.room_lookup",
        "worker.room_lookup",
        "worker.websocket_forward",
        "room.rpc",
        "room.broadcast",
        "room.websocket_load",
        "room.websocket_ticket",
        "room.websocket_setup",
        "room.websocket_push",
    }
)
_ERROR_TYPES = frozenset(
    {
        "AttributeError",
        "Exception",
        "KeyError",
        "OSError",
        "RuntimeError",
        "TypeError",
        "ValueError",
    }
)


def log_unexpected(
    operation: str,
    exc: BaseException,
    *,
    revision: int | None = None,
) -> None:
    """Log an allow-listed boundary and exception category, never its values.

    Exception messages, arguments, request data, capabilities, room/player IDs,
    and socket attachments are intentionally excluded. Logging is best effort
    and can never replace the original public behavior.
    """

    safe_operation = operation if operation in _OPERATIONS else "unknown"
    raw_error_type = type(exc).__name__
    error_type = raw_error_type if raw_error_type in _ERROR_TYPES else "Exception"
    event: dict[str, str | int] = {
        "errorType": error_type,
        "event": "unexpectedError",
        "operation": safe_operation,
    }
    if type(revision) is int and revision >= 0:
        event["revision"] = revision
    try:
        _LOGGER.error(
            json.dumps(
                event,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except Exception:
        pass


__all__ = ["log_unexpected"]
