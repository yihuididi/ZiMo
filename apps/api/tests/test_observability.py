from __future__ import annotations

import asyncio
import json

from starlette.requests import Request

from app import http_api
from app import observability


class CapturingLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def error(self, message: str) -> None:
        self.messages.append(message)


def test_unexpected_log_is_structured_and_excludes_exception_values(
    monkeypatch,
) -> None:
    logger = CapturingLogger()
    monkeypatch.setattr(observability, "_LOGGER", logger)
    secret = "Bearer super-secret-player-token"

    observability.log_unexpected(
        "room.rpc",
        RuntimeError(f"request failed with {secret}"),
        revision=17,
    )

    assert len(logger.messages) == 1
    assert json.loads(logger.messages[0]) == {
        "errorType": "RuntimeError",
        "event": "unexpectedError",
        "operation": "room.rpc",
        "revision": 17,
    }
    assert secret not in logger.messages[0]
    assert "request failed" not in logger.messages[0]


def test_unexpected_log_normalizes_untrusted_operation_and_exception_type(
    monkeypatch,
) -> None:
    logger = CapturingLogger()
    monkeypatch.setattr(observability, "_LOGGER", logger)
    secret = "ticket.secret-capability"
    SecretNamedError = type(secret, (Exception,), {})

    observability.log_unexpected(secret, SecretNamedError("hidden"), revision=-1)

    assert json.loads(logger.messages[0]) == {
        "errorType": "Exception",
        "event": "unexpectedError",
        "operation": "unknown",
    }
    assert secret not in logger.messages[0]


def test_logging_failure_never_replaces_public_error(monkeypatch) -> None:
    class BrokenLogger:
        def error(self, _message: str) -> None:
            raise RuntimeError("logging unavailable")

    monkeypatch.setattr(observability, "_LOGGER", BrokenLogger())

    assert observability.log_unexpected("http.exception", ValueError("secret")) is None


def test_http_boundary_keeps_redacted_response_and_logs_once(monkeypatch) -> None:
    logger = CapturingLogger()
    monkeypatch.setattr(observability, "_LOGGER", logger)
    secret = "player-token-do-not-log"
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/rooms/" + "a" * 64,
            "raw_path": b"/rooms/" + b"a" * 64,
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 443),
        }
    )

    response = asyncio.run(
        http_api.unexpected_exception_handler(
            request,
            RuntimeError(f"failed while handling {secret}"),
        )
    )

    assert response.status_code == 500
    assert json.loads(response.body) == {
        "error": {
            "code": "internalError",
            "message": "The request could not be completed.",
        }
    }
    assert len(logger.messages) == 1
    assert json.loads(logger.messages[0]) == {
        "errorType": "RuntimeError",
        "event": "unexpectedError",
        "operation": "http.exception",
    }
    assert secret not in logger.messages[0]
