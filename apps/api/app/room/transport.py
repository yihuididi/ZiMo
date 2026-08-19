"""Stable HTTP, RPC, and WebSocket wire primitives for room adapters."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workers import Response as WorkerResponse


NATIVE_ROOM_ID = re.compile(r"^[0-9a-f]{64}$")
CAPABILITY = re.compile(r"^[A-Za-z0-9_-]{43}$")
COMMAND_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
ROOM_PATH_PREFIX = "/rooms"
WS_PROTOCOL = "mahjong.v1"
TICKET_PROTOCOL_PREFIX = "ticket."


class ApiProblem(Exception):
    """A client-safe public API failure."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        current_revision: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.current_revision = current_revision
        super().__init__(message)

    def content(self) -> dict[str, dict[str, str | int]]:
        error: dict[str, str | int] = {
            "code": self.code,
            "message": self.message,
        }
        if self.current_revision is not None:
            error["currentRevision"] = self.current_revision
        return {"error": error}


def parse_bearer(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, separator, credential = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not CAPABILITY.fullmatch(credential)
    ):
        return None
    return credential


async def rpc_call(stub: Any, method_name: str, *args: Any) -> Any:
    raw = await getattr(stub, method_name)(*args)
    try:
        envelope = json.loads(str(raw))
    except (TypeError, ValueError) as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("room RPC returned invalid JSON") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("ok"), bool):
        raise RuntimeError("room RPC returned an invalid envelope")
    if envelope["ok"]:
        if "data" not in envelope:
            raise RuntimeError("room RPC success omitted data")
        return envelope["data"]

    error = envelope.get("error")
    if not isinstance(error, dict):
        raise RuntimeError("room RPC failure omitted error")
    status_code = error.get("status")
    code = error.get("code")
    message = error.get("message")
    current_revision = error.get("currentRevision")
    if (
        type(status_code) is not int
        or not isinstance(code, str)
        or not isinstance(message, str)
        or (current_revision is not None and type(current_revision) is not int)
    ):
        raise RuntimeError("room RPC returned an invalid error")
    raise ApiProblem(
        status_code,
        code,
        message,
        current_revision=current_revision,
    )


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_data(value: Any) -> Any:
    if hasattr(value, "canonical_data"):
        return value.canonical_data()
    if hasattr(value, "canonical_json"):
        return json.loads(value.canonical_json())
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict | list | tuple | bool | int | float) or value is None:
        return value
    raise TypeError(f"unsupported room result type: {type(value).__name__}")


def rpc_success(value: Any) -> str:
    return canonical_json({"data": canonical_data(value), "ok": True})


def service_error_data(exc: Exception) -> dict[str, Any] | None:
    """Extract only the explicitly safe room-service exception surface."""

    status_code = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None)
    current_revision = getattr(exc, "current_revision", None)
    if (
        type(status_code) is not int
        or not isinstance(code, str)
        or not isinstance(message, str)
        or (current_revision is not None and type(current_revision) is not int)
    ):
        return None
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "status": status_code,
    }
    if current_revision is not None:
        error["currentRevision"] = current_revision
    return error


def rpc_failure(exc: Exception) -> str | None:
    error = service_error_data(exc)
    return None if error is None else canonical_json({"error": error, "ok": False})


def method_text(request: Any) -> str:
    method = request.method
    return str(getattr(method, "value", method)).upper()


def request_header(request: Any, name: str) -> str | None:
    value = request.headers.get(name)
    return None if value is None else str(value)


def socket_ticket_protocol(request: Any) -> str | None:
    raw = request_header(request, "sec-websocket-protocol")
    if raw is None:
        return None
    protocols = [part.strip() for part in raw.split(",") if part.strip()]
    if len(protocols) != 2 or protocols.count(WS_PROTOCOL) != 1:
        return None
    ticket_protocols = [
        protocol
        for protocol in protocols
        if protocol.startswith(TICKET_PROTOCOL_PREFIX)
    ]
    if len(ticket_protocols) != 1:
        return None
    ticket = ticket_protocols[0][len(TICKET_PROTOCOL_PREFIX) :]
    return ticket if CAPABILITY.fullmatch(ticket) else None


def worker_problem(
    status_code: int,
    code: str,
    message: str,
    *,
    current_revision: int | None = None,
) -> WorkerResponse:
    from workers import Response as WorkerResponse

    problem = ApiProblem(
        status_code,
        code,
        message,
        current_revision=current_revision,
    )
    return WorkerResponse(
        canonical_json(problem.content()),
        status=status_code,
        headers={
            "Cache-Control": "no-store",
            "Content-Type": "application/json",
        },
    )


__all__ = [
    "ApiProblem",
    "CAPABILITY",
    "COMMAND_ID",
    "NATIVE_ROOM_ID",
    "ROOM_PATH_PREFIX",
    "TICKET_PROTOCOL_PREFIX",
    "WS_PROTOCOL",
    "canonical_data",
    "canonical_json",
    "method_text",
    "parse_bearer",
    "request_header",
    "rpc_call",
    "rpc_failure",
    "rpc_success",
    "service_error_data",
    "socket_ticket_protocol",
    "worker_problem",
]
