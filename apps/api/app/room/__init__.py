"""Stable facade for platform-neutral room orchestration."""

from __future__ import annotations

from .codec import (
    canonical_json as _canonical_json,
    capability_hash as _capability_hash,
    command_fingerprint as _command_fingerprint,
    derive_rotated_invite as _derive_rotated_invite,
    lobby_service_error as _lobby_service_error,
    parse_complete_config as _parse_complete_config,
    project_event as _project_event,
    require_non_negative_int as _require_non_negative_int,
    require_text as _require_text,
    stored_command_result as _stored_command_result,
)
from .contracts import (
    AuthenticatedPlayer,
    CommandResult,
    CommandViewResult,
    DISCONNECT_GRACE_MS,
    IssuedSocketTicket,
    PlayerSession,
    ProjectedEvents,
    ProjectedRoomEvent,
    RoomCreation,
    RoomServiceError,
    SOCKET_TICKET_TTL_MS,
    SessionEndedResult,
)
from .orchestrator import RoomOrchestrator


__all__ = [
    "AuthenticatedPlayer",
    "CommandResult",
    "CommandViewResult",
    "DISCONNECT_GRACE_MS",
    "IssuedSocketTicket",
    "PlayerSession",
    "ProjectedEvents",
    "ProjectedRoomEvent",
    "RoomCreation",
    "RoomOrchestrator",
    "RoomServiceError",
    "SOCKET_TICKET_TTL_MS",
    "SessionEndedResult",
]
