"""Cross-record and canonical snapshot invariants for room persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

if __package__ == "persistence":  # Python Workers load from the app directory.
    from game import RoomState
else:
    from ..game import RoomState

from .errors import CorruptRoomStateError, PlayerProjectionError
from .records import (
    LobbyAuditPayload,
    PlayerPresenceRecord,
    PlayerRecord,
    ProcessedCommandRecord,
    ProjectedAuditEvent,
    RoomCredentialRecord,
    RoomInitializedAuditPayload,
    RoomStateCommittedAuditPayload,
    RoomStateRecord,
    SocketTicketRecord,
    StoredAuditEvent,
    _canonical_json_value,
    _identity_text,
    _require_non_negative_int,
    _require_positive_int,
    _validate_event,
    _validate_player,
    _validate_player_presence,
)
from .sql import row_value as _row_value


def _record_from_state(state: RoomState) -> RoomStateRecord:
    if not isinstance(state, RoomState):
        raise TypeError("state must be a RoomState")

    try:
        snapshot_json = state.canonical_json()
    except Exception as exc:
        raise ValueError("RoomState failed canonical serialization") from exc
    if not isinstance(snapshot_json, str):
        raise TypeError("RoomState.canonical_json() must return str")
    try:
        decoded_snapshot = json.loads(snapshot_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("RoomState.canonical_json() returned invalid JSON") from exc
    if not isinstance(decoded_snapshot, Mapping):
        raise ValueError("canonical room snapshot must be a JSON object")

    try:
        validated_state = RoomState.model_validate_json(snapshot_json, strict=True)
    except Exception as exc:
        raise ValueError(
            "RoomState canonical JSON failed strict domain validation"
        ) from exc
    validated_snapshot_json = validated_state.canonical_json()
    if validated_snapshot_json != snapshot_json:
        raise ValueError("RoomState canonical JSON changed after strict validation")
    if not _strict_value_equivalent(validated_state, state):
        raise ValueError(
            "RoomState differs from its strict canonical reconstruction"
        )

    room_id = _identity_text(validated_state.room_id, "room_id")
    ruleset_id = _identity_text(validated_state.ruleset_id, "ruleset_id")
    ruleset_version = _identity_text(
        validated_state.ruleset_version, "ruleset_version"
    )
    state_schema_version = _require_positive_int(
        validated_state.state_schema_version, "state_schema_version"
    )
    revision = _require_non_negative_int(validated_state.revision, "revision")
    created_at_ms = _require_non_negative_int(
        validated_state.created_at_ms, "created_at_ms"
    )
    updated_at_ms = _require_non_negative_int(
        validated_state.updated_at_ms, "updated_at_ms"
    )
    if updated_at_ms < created_at_ms:
        raise ValueError("updated_at_ms must be at or after created_at_ms")

    return RoomStateRecord(
        state=validated_state,
        snapshot_json=validated_snapshot_json,
        room_id=room_id,
        ruleset_id=ruleset_id,
        ruleset_version=ruleset_version,
        state_schema_version=state_schema_version,
        revision=revision,
        config_json=_canonical_json_value(validated_state.config, "config"),
        created_at_ms=created_at_ms,
        updated_at_ms=updated_at_ms,
    )


def _record_from_row(row: Any) -> RoomStateRecord:
    snapshot_json = str(_row_value(row, "snapshot_json"))
    try:
        state = RoomState.model_validate_json(snapshot_json, strict=True)
    except Exception as exc:
        raise CorruptRoomStateError("stored room snapshot is invalid") from exc
    canonical_record = _record_from_state(state)
    if canonical_record.snapshot_json != snapshot_json:
        raise CorruptRoomStateError("stored room snapshot is not canonical JSON")

    persisted = RoomStateRecord(
        state=canonical_record.state,
        snapshot_json=snapshot_json,
        room_id=str(_row_value(row, "room_id")),
        ruleset_id=str(_row_value(row, "ruleset_id")),
        ruleset_version=str(_row_value(row, "ruleset_version")),
        state_schema_version=int(_row_value(row, "state_schema_version")),
        revision=int(_row_value(row, "revision")),
        config_json=str(_row_value(row, "config_json")),
        created_at_ms=int(_row_value(row, "created_at_ms")),
        updated_at_ms=int(_row_value(row, "updated_at_ms")),
    )
    metadata_fields = (
        "room_id",
        "ruleset_id",
        "ruleset_version",
        "state_schema_version",
        "revision",
        "config_json",
        "created_at_ms",
        "updated_at_ms",
    )
    mismatches = [
        name
        for name in metadata_fields
        if getattr(persisted, name) != getattr(canonical_record, name)
    ]
    if mismatches:
        raise CorruptRoomStateError(
            "room_state metadata does not match canonical snapshot: "
            + ", ".join(mismatches)
        )
    return persisted


def _validate_room_credential_transition(
    previous: RoomCredentialRecord, candidate: RoomCredentialRecord
) -> None:
    if candidate.created_at_ms != previous.created_at_ms:
        raise PlayerProjectionError("invite credential created_at_ms is immutable")
    if candidate.invite_generation != previous.invite_generation + 1:
        raise PlayerProjectionError("invite generation must advance exactly once")
    if candidate.invite_token_hash == previous.invite_token_hash:
        raise PlayerProjectionError("rotated invite token hash must change")
    if candidate.updated_at_ms < previous.updated_at_ms:
        raise PlayerProjectionError("invite credential timestamp cannot regress")


def _validate_audit_events(
    events: Sequence[ProjectedAuditEvent], record: RoomStateRecord
) -> None:
    for event in events:
        if type(event) is not ProjectedAuditEvent:
            raise TypeError(
                "persisted audit input must be an exact ProjectedAuditEvent"
            )
        _validate_event(event)
        if (
            event.payload.room_id != record.room_id
            or event.payload.revision != record.revision
        ):
            raise ValueError(
                "audit payload identity/revision must match committed room state"
            )


def _validate_stored_event_history(
    events: Sequence[StoredAuditEvent],
    canonical: RoomStateRecord | None,
) -> None:
    """Validate the public log against canonical room identity and chronology."""

    if canonical is None:
        if events:
            raise CorruptRoomStateError(
                "public audit events exist without canonical room state"
            )
        return

    previous_revision = -1
    previous_created_at_ms = -1
    initialized_seen = False
    committed_revisions: set[int] = set()
    for expected_sequence, event in enumerate(events, start=1):
        if event.public_sequence != expected_sequence:
            raise CorruptRoomStateError(
                "public audit event sequence is not contiguous"
            )
        if event.payload.room_id != canonical.room_id:
            raise CorruptRoomStateError(
                "audit payload room_id does not match canonical room state"
            )
        if event.revision != event.payload.revision:
            raise CorruptRoomStateError(
                "audit payload revision does not match its indexed revision"
            )
        if event.revision > canonical.revision:
            raise CorruptRoomStateError(
                "audit event revision exceeds canonical room revision"
            )
        if event.revision < previous_revision:
            raise CorruptRoomStateError(
                "audit event revisions are not chronological"
            )
        if event.created_at_ms < previous_created_at_ms:
            raise CorruptRoomStateError(
                "audit event timestamps are not chronological"
            )

        if type(event.payload) is RoomInitializedAuditPayload:
            if initialized_seen or expected_sequence != 1:
                raise CorruptRoomStateError(
                    "roomInitialized must be the first and only initialization event"
                )
            initialized_seen = True
        elif type(event.payload) is RoomStateCommittedAuditPayload:
            if event.revision in committed_revisions:
                raise CorruptRoomStateError(
                    "roomStateCommitted audit revisions must be unique"
                )
            committed_revisions.add(event.revision)
        elif type(event.payload) is LobbyAuditPayload:
            # Several separately useful public facts (for example a departure
            # and deterministic host transfer) may share one canonical commit.
            pass
        else:  # Defensive: StoredAuditEvent construction is otherwise public.
            raise CorruptRoomStateError("stored audit payload type is not allow-listed")

        previous_revision = event.revision
        previous_created_at_ms = event.created_at_ms


def _strict_value_equivalent(left: Any, right: Any) -> bool:
    """Compare validated domain values without string-enum coercion equality."""

    if type(left) is not type(right):
        return False
    model_fields = getattr(type(left), "model_fields", None)
    if isinstance(model_fields, Mapping):
        missing = object()
        return all(
            _strict_value_equivalent(
                getattr(left, field_name, missing),
                getattr(right, field_name, missing),
            )
            for field_name in model_fields
        )
    if isinstance(left, tuple):
        return len(left) == len(right) and all(
            _strict_value_equivalent(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_value_equivalent(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, Mapping):
        return left.keys() == right.keys() and all(
            _strict_value_equivalent(left[key], right[key]) for key in left
        )
    return bool(left == right)


def _external_roster_signature(state: RoomState) -> tuple[tuple[Any, ...], ...]:
    players_by_id = {
        _identity_text(player.player_id, "player_id"): player
        for player in state.players
    }
    signature: list[tuple[Any, ...]] = []
    for seat in state.seats:
        controller = seat.controller
        if controller is None or getattr(controller, "type", None) != "external":
            continue
        player_id = _identity_text(controller.player_id, "player_id")
        player = players_by_id[player_id]
        role = getattr(player.role, "value", player.role)
        signature.append(
            (
                player_id,
                _identity_text(seat.seat_id, "seat_id"),
                player.display_name,
                str(role),
                player.joined_at_ms,
                _canonical_json_value(controller, "seat controller"),
            )
        )
    return tuple(sorted(signature))


def _validate_players_against_state(
    players: Sequence[PlayerRecord],
    state: RoomState,
    *,
    allow_historical: bool,
) -> None:
    expected = {
        signature[0]: signature for signature in _external_roster_signature(state)
    }
    supplied: dict[str, PlayerRecord] = {}
    for player in players:
        if type(player) is not PlayerRecord:
            raise TypeError("players projection must contain exact PlayerRecord values")
        _validate_player(player)
        if player.player_id in supplied:
            raise PlayerProjectionError(
                f"duplicate player projection: {player.player_id!r}"
            )
        supplied[player.player_id] = player

    active = {
        player_id: player
        for player_id, player in supplied.items()
        if player.left_at_ms is None
    }
    historical = {
        player_id: player
        for player_id, player in supplied.items()
        if player.left_at_ms is not None
    }
    if historical and not allow_historical:
        raise PlayerProjectionError(
            "initial players projection cannot contain historical rows"
        )
    if set(active) != set(expected):
        raise PlayerProjectionError(
            "active players projection must exactly match the external player roster"
        )
    if set(historical).intersection(expected):
        raise PlayerProjectionError(
            "a historical player cannot remain in the active room roster"
        )

    for player_id, player in active.items():
        (
            _,
            seat_id,
            display_name,
            role,
            joined_at_ms,
            controller_json,
        ) = expected[player_id]
        mismatches: list[str] = []
        for field, actual, expected_value in (
            ("seat_id", player.seat_id, seat_id),
            ("display_name", player.display_name, display_name),
            ("role", player.role, role),
            ("joined_at_ms", player.joined_at_ms, joined_at_ms),
            ("controller_json", player.controller_json, controller_json),
        ):
            if actual != expected_value:
                mismatches.append(field)
        if player.left_at_ms is not None:
            mismatches.append("left_at_ms")
        if mismatches:
            raise PlayerProjectionError(
                f"player {player_id!r} projection disagrees with room state: "
                + ", ".join(mismatches)
            )


def _merge_player_lifecycle(
    existing: Sequence[PlayerRecord],
    supplied: Sequence[PlayerRecord],
    state: RoomState,
    *,
    revocation_at_ms: int,
) -> tuple[PlayerRecord, ...]:
    """Merge a complete active roster while retaining immutable revoked rows.

    Existing security counters and timestamps never regress.  A removed player
    is revoked at this commit and retained as history; only active records can
    subsequently back idempotency commands or socket tickets.
    """

    _validate_players_against_state(supplied, state, allow_historical=True)
    existing_by_id = {player.player_id: player for player in existing}
    supplied_by_id = {player.player_id: player for player in supplied}
    expected_active_ids = {
        signature[0] for signature in _external_roster_signature(state)
    }
    merged: dict[str, PlayerRecord] = {}

    for player_id, previous in existing_by_id.items():
        candidate = supplied_by_id.get(player_id)
        if previous.left_at_ms is not None:
            if candidate is not None and candidate != previous:
                raise PlayerProjectionError(
                    f"revoked player {player_id!r} history is immutable"
                )
            merged[player_id] = previous
            continue

        if player_id not in expected_active_ids:
            if candidate is None:
                revoked_at_ms = max(revocation_at_ms, previous.updated_at_ms)
                candidate = replace(
                    previous,
                    auth_generation=previous.auth_generation + 1,
                    updated_at_ms=revoked_at_ms,
                    left_at_ms=revoked_at_ms,
                )
            _validate_player_security_transition(
                previous,
                candidate,
                requires_revocation=True,
                revocation_at_ms=revocation_at_ms,
            )
            merged[player_id] = candidate
            continue

        if candidate is None:
            raise PlayerProjectionError(
                f"active player {player_id!r} is missing from supplied projections"
            )
        _validate_player_security_transition(
            previous,
            candidate,
            requires_revocation=False,
            revocation_at_ms=revocation_at_ms,
        )
        merged[player_id] = candidate

    for player_id, candidate in supplied_by_id.items():
        if player_id in merged:
            continue
        if candidate.left_at_ms is not None:
            raise PlayerProjectionError(
                f"unknown historical player projection: {player_id!r}"
            )
        merged[player_id] = candidate

    result = tuple(sorted(merged.values(), key=lambda player: player.player_id))
    _validate_players_against_state(result, state, allow_historical=True)
    return result


def _validate_player_security_transition(
    previous: PlayerRecord,
    candidate: PlayerRecord,
    *,
    requires_revocation: bool,
    revocation_at_ms: int,
) -> None:
    if candidate.joined_at_ms != previous.joined_at_ms:
        raise PlayerProjectionError("player joined_at_ms is immutable")
    if candidate.auth_generation < previous.auth_generation:
        raise PlayerProjectionError("player auth_generation cannot regress")
    if candidate.updated_at_ms < previous.updated_at_ms:
        raise PlayerProjectionError("player updated_at_ms cannot regress")
    if (
        candidate.token_hash != previous.token_hash
        and candidate.auth_generation <= previous.auth_generation
    ):
        raise PlayerProjectionError(
            "rotating a player token requires a newer auth_generation"
        )

    if requires_revocation:
        immutable_public_fields = (
            "seat_id",
            "display_name",
            "role",
            "controller_json",
        )
        if any(
            getattr(candidate, field) != getattr(previous, field)
            for field in immutable_public_fields
        ):
            raise PlayerProjectionError(
                "revoked player public history must match its active record"
            )
        if candidate.left_at_ms is None:
            raise PlayerProjectionError("removed player must have left_at_ms")
        if candidate.left_at_ms < revocation_at_ms:
            raise PlayerProjectionError(
                "removed player left_at_ms cannot precede the room commit"
            )
        if candidate.auth_generation <= previous.auth_generation:
            raise PlayerProjectionError(
                "revoking a player requires a newer auth_generation"
            )
    elif candidate.left_at_ms is not None:
        raise PlayerProjectionError("active player cannot have left_at_ms")


def _validate_security_references(
    commands: Sequence[ProcessedCommandRecord],
    tickets: Sequence[SocketTicketRecord],
    players: Sequence[PlayerRecord],
    *,
    allowed_command_player_ids: set[str],
) -> None:
    active = {
        player.player_id: player
        for player in players
        if player.left_at_ms is None
    }
    for command in commands:
        if command.player_id not in allowed_command_player_ids:
            raise PlayerProjectionError(
                "processed command must reference an active player or the player "
                "revoked by this commit"
            )
    for ticket in tickets:
        player = active.get(ticket.player_id)
        if player is None:
            raise PlayerProjectionError(
                "socket ticket must reference an active player"
            )
        if ticket.auth_generation != player.auth_generation:
            raise PlayerProjectionError(
                "socket ticket auth_generation must match its active player"
            )


def _validate_presence_references(
    records: Sequence[PlayerPresenceRecord],
    players: Sequence[PlayerRecord],
) -> None:
    active = {
        player.player_id: player
        for player in players
        if player.left_at_ms is None
    }
    seen_ids: set[str] = set()
    for presence in records:
        if type(presence) is not PlayerPresenceRecord:
            raise TypeError("presence must contain exact PlayerPresenceRecord values")
        _validate_player_presence(presence)
        if presence.player_id in seen_ids:
            raise ValueError(
                f"duplicate player presence projection: {presence.player_id!r}"
            )
        seen_ids.add(presence.player_id)
        player = active.get(presence.player_id)
        if player is None:
            raise PlayerProjectionError(
                "player presence must reference an active player"
            )
        if player.auth_generation != presence.auth_generation:
            raise PlayerProjectionError(
                "player presence auth_generation must match its active player"
            )


def _normalize_player_identities(
    identities: Sequence[tuple[str, int]],
) -> tuple[tuple[str, int], ...]:
    normalized: set[tuple[str, int]] = set()
    for identity in identities:
        if type(identity) is not tuple or len(identity) != 2:
            raise TypeError(
                "player identities must be (player_id, auth_generation) tuples"
            )
        player_id = _identity_text(identity[0], "player_id")
        generation = _require_non_negative_int(identity[1], "auth_generation")
        normalized.add((player_id, generation))
    return tuple(sorted(normalized))


def _validate_connected_presence_references(
    identities: Sequence[tuple[str, int]],
    players: Sequence[PlayerRecord],
) -> None:
    active = {
        (player.player_id, player.auth_generation)
        for player in players
        if player.left_at_ms is None
    }
    if any(identity not in active for identity in identities):
        raise PlayerProjectionError(
            "connected player presence must reference an active auth generation"
        )
