"""Validated records and canonical codecs for persistence projections."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, TypeAlias, cast

if __package__ == "persistence":  # Python Workers load from the app directory.
    from game import RoomState
else:
    from ..game import RoomState

from .errors import CorruptRoomStateError
from .sql import row_value as _row_value


@dataclass(frozen=True, slots=True)
class PlayerPresenceRecord:
    """Durable disconnected state for one active authentication generation."""

    player_id: str
    auth_generation: int
    disconnected_at_ms: int
    disconnect_expires_at_ms: int | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_id", _identity_text(self.player_id, "player_id")
        )
        _validate_player_presence(self)


@dataclass(frozen=True, slots=True)
class PlayerRecord:
    """Authentication data plus a queryable projection of a room player."""

    player_id: str
    display_name: str
    role: str
    controller_json: str
    token_hash: str
    auth_generation: int
    joined_at_ms: int
    updated_at_ms: int
    seat_id: str | None = None
    left_at_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_id", _identity_text(self.player_id, "player_id")
        )
        if self.seat_id is not None:
            object.__setattr__(
                self, "seat_id", _identity_text(self.seat_id, "seat_id")
            )
        _validate_player(self)
        object.__setattr__(
            self,
            "controller_json",
            _canonicalize_json_text(self.controller_json, "controller_json"),
        )


@dataclass(frozen=True, slots=True)
class RoomCredentialRecord:
    """Hashed, rotatable room invite capability; raw values never persist."""

    invite_token_hash: str
    invite_generation: int
    created_at_ms: int
    updated_at_ms: int

    def __post_init__(self) -> None:
        _validate_room_credential(self)


@dataclass(frozen=True, slots=True)
class RoomInitializedAuditPayload:
    """Allow-listed public fact that a canonical room was initialized."""

    event_type: ClassVar[str] = "roomInitialized"
    room_id: str
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "room_id", _identity_text(self.room_id, "room_id"))
        _require_non_negative_int(self.revision, "revision")
        if self.revision != 0:
            raise ValueError("roomInitialized audit revision must be zero")


@dataclass(frozen=True, slots=True)
class RoomStateCommittedAuditPayload:
    """Allow-listed public fact that canonical state advanced one revision."""

    event_type: ClassVar[str] = "roomStateCommitted"
    room_id: str
    previous_revision: int
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "room_id", _identity_text(self.room_id, "room_id"))
        _require_non_negative_int(self.previous_revision, "previous_revision")
        _require_non_negative_int(self.revision, "revision")
        if self.revision != self.previous_revision + 1:
            raise ValueError("audit revision must equal previous_revision + 1")


_LOBBY_AUDIT_EVENT_TYPES = frozenset(
    {
        "roomCreated",
        "playerJoined",
        "playerReadinessChanged",
        "botAdded",
        "botsFilled",
        "botRemoved",
        "playerRemoved",
        "playerLeft",
        "hostTransferred",
        "inviteRotated",
        "matchStarted",
        "configUpdated",
    }
)


@dataclass(frozen=True, slots=True)
class LobbyAuditPayload:
    """Allow-listed public lobby fact with canonical, secret-free details."""

    event_type: str
    room_id: str
    revision: int
    details_json: str = "{}"

    def __post_init__(self) -> None:
        if self.event_type not in _LOBBY_AUDIT_EVENT_TYPES:
            raise ValueError("lobby audit event type is not allow-listed")
        object.__setattr__(self, "room_id", _identity_text(self.room_id, "room_id"))
        _require_non_negative_int(self.revision, "revision")
        canonical = _canonicalize_json_text(self.details_json, "details_json")
        details = json.loads(canonical)
        if type(details) is not dict:
            raise ValueError("lobby audit details must be a JSON object")
        _validate_public_event_details(details)
        object.__setattr__(self, "details_json", canonical)

    @property
    def details(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.details_json))


SafeAuditPayload: TypeAlias = (
    RoomInitializedAuditPayload
    | RoomStateCommittedAuditPayload
    | LobbyAuditPayload
)


_SAFE_AUDIT_PAYLOAD_TYPES = (
    RoomInitializedAuditPayload,
    RoomStateCommittedAuditPayload,
    LobbyAuditPayload,
)


@dataclass(frozen=True, slots=True)
class ProjectedAuditEvent:
    """An allow-listed, secret-free event ready for public audit storage."""

    payload: SafeAuditPayload
    created_at_ms: int

    def __post_init__(self) -> None:
        _validate_event(self)

    @property
    def event_type(self) -> str:
        return self.payload.event_type

    @property
    def event_json(self) -> str:
        return _audit_payload_json(self.payload)


@dataclass(frozen=True, slots=True)
class StoredAuditEvent(ProjectedAuditEvent):
    """A projected event after the repository assigns its public sequence."""

    public_sequence: int
    revision: int


@dataclass(frozen=True, slots=True)
class ProcessedCommandRecord:
    """A durable idempotency result scoped to one room-local player."""

    player_id: str
    command_id: str
    request_fingerprint: str
    revision: int
    result_json: str
    processed_at_ms: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_id", _identity_text(self.player_id, "player_id")
        )
        object.__setattr__(
            self, "command_id", _identity_text(self.command_id, "command_id")
        )
        _validate_processed_command(self)
        object.__setattr__(
            self,
            "result_json",
            _canonicalize_json_text(self.result_json, "result_json"),
        )


@dataclass(frozen=True, slots=True)
class SocketTicketRecord:
    """A hashed, single-use WebSocket ticket projection."""

    ticket_hash: str
    player_id: str
    auth_generation: int
    expires_at_ms: int
    created_at_ms: int
    consumed_at_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_id", _identity_text(self.player_id, "player_id")
        )
        _validate_socket_ticket(self)


@dataclass(frozen=True, slots=True)
class RoomStateRecord:
    """Canonical state together with the duplicated indexed metadata."""

    state: RoomState
    snapshot_json: str
    room_id: str
    ruleset_id: str
    ruleset_version: str
    state_schema_version: int
    revision: int
    config_json: str
    created_at_ms: int
    updated_at_ms: int


def _canonical_json_value(value: Any, name: str) -> str:
    if isinstance(value, str):
        return _canonicalize_json_text(value, name)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        value = model_dump(mode="json", by_alias=True, exclude_none=False)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc


def _canonicalize_json_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a JSON string")
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain valid JSON") from exc
    return _canonical_json_value(decoded, name)


def _player_record_from_row(row: Any) -> PlayerRecord:
    left_at_ms = _row_value(row, "left_at_ms")
    return PlayerRecord(
        player_id=str(_row_value(row, "player_id")),
        seat_id=_optional_text(_row_value(row, "seat_id")),
        display_name=str(_row_value(row, "display_name")),
        role=str(_row_value(row, "role")),
        controller_json=str(_row_value(row, "controller_json")),
        token_hash=str(_row_value(row, "token_hash")),
        auth_generation=int(_row_value(row, "auth_generation")),
        joined_at_ms=int(_row_value(row, "joined_at_ms")),
        updated_at_ms=int(_row_value(row, "updated_at_ms")),
        left_at_ms=None if left_at_ms is None else int(left_at_ms),
    )


def _player_presence_from_row(row: Any) -> PlayerPresenceRecord:
    expires_at_ms = _row_value(row, "disconnect_expires_at_ms")
    return PlayerPresenceRecord(
        player_id=str(_row_value(row, "player_id")),
        auth_generation=int(_row_value(row, "auth_generation")),
        disconnected_at_ms=int(_row_value(row, "disconnected_at_ms")),
        disconnect_expires_at_ms=(
            None if expires_at_ms is None else int(expires_at_ms)
        ),
    )


def _validate_player_presence(presence: PlayerPresenceRecord) -> None:
    _require_text(presence.player_id, "player_id")
    _require_non_negative_int(presence.auth_generation, "auth_generation")
    _require_non_negative_int(presence.disconnected_at_ms, "disconnected_at_ms")
    if presence.disconnect_expires_at_ms is not None:
        _require_non_negative_int(
            presence.disconnect_expires_at_ms, "disconnect_expires_at_ms"
        )
        if presence.disconnect_expires_at_ms < presence.disconnected_at_ms:
            raise ValueError(
                "disconnect_expires_at_ms cannot precede disconnected_at_ms"
            )


def _validate_player(player: PlayerRecord) -> None:
    _require_text(player.player_id, "player_id")
    _require_text(player.display_name, "display_name")
    _require_text(player.role, "role")
    _require_sha256_hex(player.token_hash, "token_hash")
    if player.seat_id is not None:
        _require_text(player.seat_id, "seat_id")
    _canonicalize_json_text(player.controller_json, "controller_json")
    _require_non_negative_int(player.auth_generation, "auth_generation")
    _require_non_negative_int(player.joined_at_ms, "joined_at_ms")
    _require_non_negative_int(player.updated_at_ms, "updated_at_ms")
    if player.updated_at_ms < player.joined_at_ms:
        raise ValueError("player updated_at_ms must be at or after joined_at_ms")
    if player.left_at_ms is not None:
        _require_non_negative_int(player.left_at_ms, "left_at_ms")
        if player.left_at_ms < player.joined_at_ms:
            raise ValueError("player left_at_ms must be at or after joined_at_ms")
        if player.updated_at_ms < player.left_at_ms:
            raise ValueError("player updated_at_ms must be at or after left_at_ms")


def _validate_room_credential(record: RoomCredentialRecord) -> None:
    _require_sha256_hex(record.invite_token_hash, "invite_token_hash")
    _require_non_negative_int(record.invite_generation, "invite_generation")
    _require_non_negative_int(record.created_at_ms, "created_at_ms")
    _require_non_negative_int(record.updated_at_ms, "updated_at_ms")
    if record.updated_at_ms < record.created_at_ms:
        raise ValueError("credential updated_at_ms cannot precede created_at_ms")


def _validate_public_event_details(value: Mapping[str, object]) -> None:
    forbidden_fragments = ("token", "secret", "ticket", "hash", "credential")
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("public event detail keys must be non-empty strings")
        folded = key.casefold()
        if any(fragment in folded for fragment in forbidden_fragments):
            raise ValueError("public event details cannot contain credential material")
        if item is None or isinstance(item, (str, bool)):
            continue
        if isinstance(item, int) and not isinstance(item, bool):
            continue
        raise ValueError("public event detail values must be scalar JSON values")


def _validate_event(event: ProjectedAuditEvent) -> None:
    if type(event) not in (ProjectedAuditEvent, StoredAuditEvent):
        raise TypeError("audit event type is not allow-listed")
    if type(event.payload) not in _SAFE_AUDIT_PAYLOAD_TYPES:
        raise TypeError("audit payload type is not allow-listed")
    _require_non_negative_int(event.created_at_ms, "created_at_ms")


def _audit_payload_json(payload: SafeAuditPayload) -> str:
    if type(payload) is RoomInitializedAuditPayload:
        value = {
            "type": payload.event_type,
            "roomId": payload.room_id,
            "revision": payload.revision,
        }
    elif type(payload) is RoomStateCommittedAuditPayload:
        value = {
            "type": payload.event_type,
            "roomId": payload.room_id,
            "previousRevision": payload.previous_revision,
            "revision": payload.revision,
        }
    elif type(payload) is LobbyAuditPayload:
        value = {
            "type": payload.event_type,
            "roomId": payload.room_id,
            "revision": payload.revision,
            "details": payload.details,
        }
    else:
        raise TypeError("audit payload type is not allow-listed")
    return _canonical_json_value(value, "audit payload")


def _parse_audit_payload(event_type: str, event_json: str) -> SafeAuditPayload:
    try:
        value = json.loads(event_json)
    except (TypeError, ValueError) as exc:
        raise CorruptRoomStateError("stored audit payload is invalid JSON") from exc
    if type(value) is not dict:
        raise CorruptRoomStateError("stored audit payload must be a JSON object")
    if value.get("type") != event_type:
        raise CorruptRoomStateError(
            "stored audit type column does not match its payload"
        )

    try:
        if event_type == RoomInitializedAuditPayload.event_type:
            if set(value) != {"type", "roomId", "revision"}:
                raise CorruptRoomStateError(
                    "roomInitialized audit payload contains non-public fields"
                )
            payload: SafeAuditPayload = RoomInitializedAuditPayload(
                room_id=value["roomId"],
                revision=value["revision"],
            )
        elif event_type == RoomStateCommittedAuditPayload.event_type:
            if set(value) != {
                "type",
                "roomId",
                "previousRevision",
                "revision",
            }:
                raise CorruptRoomStateError(
                    "roomStateCommitted audit payload contains non-public fields"
                )
            payload = RoomStateCommittedAuditPayload(
                room_id=value["roomId"],
                previous_revision=value["previousRevision"],
                revision=value["revision"],
            )
        elif event_type in _LOBBY_AUDIT_EVENT_TYPES:
            if set(value) != {"type", "roomId", "revision", "details"}:
                raise CorruptRoomStateError(
                    "lobby audit payload contains non-public fields"
                )
            payload = LobbyAuditPayload(
                event_type=event_type,
                room_id=value["roomId"],
                revision=value["revision"],
                details_json=_canonical_json_value(value["details"], "details"),
            )
        else:
            raise CorruptRoomStateError(
                f"stored audit event type is not allow-listed: {event_type!r}"
            )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, CorruptRoomStateError):
            raise
        raise CorruptRoomStateError("stored audit payload is invalid") from exc

    if _audit_payload_json(payload) != event_json:
        raise CorruptRoomStateError("stored audit payload is not canonical JSON")
    return payload


def _validate_processed_command(command: ProcessedCommandRecord) -> None:
    _require_text(command.player_id, "player_id")
    _require_text(command.command_id, "command_id")
    _require_text(command.request_fingerprint, "request_fingerprint")
    _require_non_negative_int(command.revision, "revision")
    _canonicalize_json_text(command.result_json, "result_json")
    _require_non_negative_int(command.processed_at_ms, "processed_at_ms")


def _validate_socket_ticket(ticket: SocketTicketRecord) -> None:
    _require_sha256_hex(ticket.ticket_hash, "ticket_hash")
    _require_text(ticket.player_id, "player_id")
    _require_non_negative_int(ticket.auth_generation, "auth_generation")
    _require_non_negative_int(ticket.expires_at_ms, "expires_at_ms")
    _require_non_negative_int(ticket.created_at_ms, "created_at_ms")
    if ticket.expires_at_ms < ticket.created_at_ms:
        raise ValueError(
            "socket ticket expires_at_ms must be at or after created_at_ms"
        )
    if ticket.consumed_at_ms is not None:
        _require_non_negative_int(ticket.consumed_at_ms, "consumed_at_ms")
        if ticket.consumed_at_ms < ticket.created_at_ms:
            raise ValueError(
                "socket ticket consumed_at_ms must be at or after created_at_ms"
            )


def _identity_text(value: Any, name: str) -> str:
    root = getattr(value, "root", None)
    if isinstance(root, str):
        value = root
    return str(_require_text(value, name))


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _require_sha256_hex(value: Any, name: str) -> str:
    result = _require_text(value, name)
    if len(result) != 64 or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise ValueError(
            f"{name} must be exactly 64 lowercase hexadecimal characters"
        )
    return result


def _require_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _require_positive_int(value: Any, name: str) -> int:
    result = _require_non_negative_int(value, name)
    if result == 0:
        raise ValueError(f"{name} must be positive")
    return result


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


__all__ = [
    "LobbyAuditPayload",
    "PlayerPresenceRecord",
    "PlayerRecord",
    "ProcessedCommandRecord",
    "ProjectedAuditEvent",
    "RoomCredentialRecord",
    "RoomInitializedAuditPayload",
    "RoomStateCommittedAuditPayload",
    "RoomStateRecord",
    "SafeAuditPayload",
    "SocketTicketRecord",
    "StoredAuditEvent",
]
