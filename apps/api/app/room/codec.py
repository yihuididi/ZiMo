"""Canonical validation, hashing, and projection helpers for room services."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from pydantic import ValidationError

if __package__.startswith("app."):
    from ..game import GameConfig
    from ..lobby import LobbyDomainError
    from ..persistence import (
        LobbyAuditPayload,
        RoomInitializedAuditPayload,
        RoomStateCommittedAuditPayload,
        StoredAuditEvent,
    )
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import GameConfig
    from lobby import LobbyDomainError
    from persistence import (
        LobbyAuditPayload,
        RoomInitializedAuditPayload,
        RoomStateCommittedAuditPayload,
        StoredAuditEvent,
    )

from .contracts import CommandResult, ProjectedRoomEvent, RoomServiceError


_INVITE_ROTATION_DOMAIN = b"zimo:invite-rotation:v1\x00"


def lobby_service_error(
    error: LobbyDomainError, *, current_revision: int | None = None
) -> RoomServiceError:
    mapping = {
        "INVALID_DISPLAY_NAME": (422, "invalidDisplayName", "The display name is invalid."),
        "DISPLAY_NAME_TAKEN": (409, "displayNameTaken", "The display name is already in use."),
        "ROOM_FULL": (409, "roomFull", "The room has no open seats."),
        "ROOM_CLOSED": (409, "roomClosed", "The room roster is frozen."),
        "HOST_REQUIRED": (403, "hostRequired", "Host permission is required."),
        "ACTION_NOT_AVAILABLE": (409, "actionNotAvailable", "The action is not available."),
        "PLAYER_NOT_FOUND": (401, "invalidPlayerToken", "Authentication is invalid."),
        "PLAYER_ID_TAKEN": (409, "playerIdTaken", "The player identity is already in use."),
    }
    status, code, message = mapping.get(
        error.code,
        (409, "roomConflict", "The room request conflicts with its current state."),
    )
    return RoomServiceError(code, status, message, current_revision=current_revision)


def parse_complete_config(config_json: str) -> GameConfig:
    if not isinstance(config_json, str):
        raise RoomServiceError("invalidConfig", 422, "The configuration is invalid.")
    aliases = {field.alias or name for name, field in GameConfig.model_fields.items()}
    try:
        value = json.loads(config_json)
        if type(value) is not dict or set(value) != aliases:
            raise ValueError("configuration shape is incomplete")
        return GameConfig.model_validate_json(config_json, strict=True)
    except (TypeError, ValueError, ValidationError) as exc:
        raise RoomServiceError(
            "invalidConfig", 422, "The configuration is invalid."
        ) from exc


def project_event(event: StoredAuditEvent) -> ProjectedRoomEvent:
    payload = event.payload
    if isinstance(payload, LobbyAuditPayload):
        details = payload.details
    elif isinstance(payload, RoomInitializedAuditPayload):
        details = {}
    elif isinstance(payload, RoomStateCommittedAuditPayload):
        details = {"previousRevision": payload.previous_revision}
    else:  # pragma: no cover
        raise RuntimeError("unsupported stored audit event")
    return ProjectedRoomEvent(
        public_sequence=event.public_sequence,
        revision=event.revision,
        type=event.event_type,
        payload=details,
        created_at_ms=event.created_at_ms,
    )


def stored_command_result(result: CommandResult, *, rotated_invite: bool) -> str:
    result_data = result.canonical_data()
    result_data.pop("inviteToken", None)
    return canonical_json({"result": result_data, "rotatedInvite": rotated_invite})


def command_fingerprint(
    command_id: str, expected_revision: int, action_id: str
) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "actionId": action_id,
                "commandId": command_id,
                "expectedRevision": expected_revision,
            }
        ).encode()
    ).hexdigest()


def derive_rotated_invite(
    player_token: str, room_id: str, player_id: str, command_id: str
) -> str:
    material = b"\x00".join(
        value.encode("utf-8") for value in (room_id, player_id, command_id)
    )
    digest = hmac.new(
        player_token.encode("utf-8"),
        _INVITE_ROTATION_DOMAIN + material,
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def capability_hash(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("capability must be a string")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def require_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


__all__ = [
    "canonical_json",
    "capability_hash",
    "command_fingerprint",
    "derive_rotated_invite",
    "lobby_service_error",
    "parse_complete_config",
    "project_event",
    "require_non_negative_int",
    "require_text",
    "stored_command_result",
]
