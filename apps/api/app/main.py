"""Stable Cloudflare Worker and Durable Object export facade."""

from __future__ import annotations

if __package__:
    from .durable_room import GameRoom
    from .http_api import app
    from .room.transport import (
        ApiProblem,
        CAPABILITY as _CAPABILITY,
        COMMAND_ID as _COMMAND_ID,
        NATIVE_ROOM_ID as _NATIVE_ROOM_ID,
        ROOM_PATH_PREFIX as _ROOM_PATH_PREFIX,
        TICKET_PROTOCOL_PREFIX as _TICKET_PROTOCOL_PREFIX,
        WS_PROTOCOL as _WS_PROTOCOL,
        canonical_data as _canonical_data,
        canonical_json as _canonical_json,
        method_text as _method_text,
        parse_bearer as _parse_bearer,
        request_header as _request_header,
        rpc_call as _rpc_call,
        rpc_failure as _rpc_failure,
        rpc_success as _rpc_success,
        service_error_data as _service_error_data,
        socket_ticket_protocol as _socket_ticket_protocol,
        worker_problem as _worker_problem,
    )
    from .worker_entry import Default
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from durable_room import GameRoom
    from http_api import app
    from room.transport import (
        ApiProblem,
        CAPABILITY as _CAPABILITY,
        COMMAND_ID as _COMMAND_ID,
        NATIVE_ROOM_ID as _NATIVE_ROOM_ID,
        ROOM_PATH_PREFIX as _ROOM_PATH_PREFIX,
        TICKET_PROTOCOL_PREFIX as _TICKET_PROTOCOL_PREFIX,
        WS_PROTOCOL as _WS_PROTOCOL,
        canonical_data as _canonical_data,
        canonical_json as _canonical_json,
        method_text as _method_text,
        parse_bearer as _parse_bearer,
        request_header as _request_header,
        rpc_call as _rpc_call,
        rpc_failure as _rpc_failure,
        rpc_success as _rpc_success,
        service_error_data as _service_error_data,
        socket_ticket_protocol as _socket_ticket_protocol,
        worker_problem as _worker_problem,
    )
    from worker_entry import Default


__all__ = ["Default", "GameRoom", "app"]
