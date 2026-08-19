"""Pure lobby roster, configuration, presence, and host transitions."""

from __future__ import annotations

import unicodedata
from collections.abc import Set

if "." in (__package__ or ""):
    from ..game import (
        ExternalSeatController,
        GameConfig,
        MatchState,
        PlayerId,
        PlayerRole,
        PlayerState,
        RoomId,
        RoomState,
        RoomStatus,
        SeatId,
        SeatState,
        standard_seats,
    )
else:  # pragma: no cover - Pyodide Worker module loading
    from game import (
        ExternalSeatController,
        GameConfig,
        MatchState,
        PlayerId,
        PlayerRole,
        PlayerState,
        RoomId,
        RoomState,
        RoomStatus,
        SeatId,
        SeatState,
        standard_seats,
    )

from .types import (
    LobbyDomainError,
    LobbyTransition,
    MAX_DISPLAY_NAME_LENGTH,
)


def normalize_display_name(value: str) -> str:
    """NFKC-normalize, strip control/format characters, and fold whitespace."""

    if not isinstance(value, str):
        raise LobbyDomainError("INVALID_DISPLAY_NAME", "display name must be text")
    normalized = unicodedata.normalize("NFKC", value)
    visible = "".join(
        character
        for character in normalized
        if unicodedata.category(character) not in {"Cc", "Cf"}
    )
    collapsed = " ".join(visible.split())
    if not collapsed:
        raise LobbyDomainError(
            "INVALID_DISPLAY_NAME", "display name must not be empty"
        )
    if len(collapsed) > MAX_DISPLAY_NAME_LENGTH:
        raise LobbyDomainError(
            "INVALID_DISPLAY_NAME",
            f"display name cannot exceed {MAX_DISPLAY_NAME_LENGTH} characters",
        )
    return collapsed


def create_lobby_room(
    room_id: RoomId | str,
    host_player_id: PlayerId | str,
    display_name: str,
    *,
    now_ms: int,
) -> RoomState:
    _require_timestamp(now_ms)
    room_id = room_id if isinstance(room_id, RoomId) else RoomId(room_id)
    player_id = (
        host_player_id
        if isinstance(host_player_id, PlayerId)
        else PlayerId(host_player_id)
    )
    name = normalize_display_name(display_name)
    seats = list(standard_seats())
    seats[0] = SeatState(
        seat_id=seats[0].seat_id,
        slot=0,
        controller=ExternalSeatController(player_id=player_id),
        occupant_name=name,
    )
    return RoomState(
        room_id=room_id,
        state_schema_version=2,
        revision=0,
        status=RoomStatus.WAITING_FOR_PLAYERS,
        seats=tuple(seats),
        players=(
            PlayerState(
                player_id=player_id,
                display_name=name,
                role=PlayerRole.HOST,
                ready=False,
                joined_at_ms=now_ms,
            ),
        ),
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
    )


def join_lobby_room(
    room: RoomState,
    player_id: PlayerId | str,
    display_name: str,
    *,
    now_ms: int,
) -> LobbyTransition:
    _require_pre_match(room)
    _require_timestamp(now_ms)
    player_id = player_id if isinstance(player_id, PlayerId) else PlayerId(player_id)
    if any(player.player_id == player_id for player in room.players):
        raise LobbyDomainError("PLAYER_ID_TAKEN", "player identity is already in use")
    name = normalize_display_name(display_name)
    _require_unique_name(room, name)
    empty = next((seat for seat in _sorted_seats(room) if seat.controller is None), None)
    if empty is None:
        raise LobbyDomainError("ROOM_FULL", "room has no open seats")

    joined_at_ms = max(now_ms, room.updated_at_ms)
    players = [player.model_copy(update={"ready": False}) for player in room.players]
    players.append(
        PlayerState(
            player_id=player_id,
            display_name=name,
            role=PlayerRole.MEMBER,
            ready=False,
            joined_at_ms=joined_at_ms,
        )
    )
    seats = [
        SeatState(
            seat_id=seat.seat_id,
            slot=seat.slot,
            controller=ExternalSeatController(player_id=player_id),
            occupant_name=name,
        )
        if seat.seat_id == empty.seat_id
        else seat
        for seat in room.seats
    ]
    state = _next_state(room, players=tuple(players), seats=tuple(seats), now_ms=now_ms)
    return LobbyTransition(
        state=state,
        event_type="playerJoined",
        event_details={"playerId": str(player_id), "seatId": str(empty.seat_id)},
    )


def update_lobby_config(
    room: RoomState,
    actor_player_id: PlayerId | str,
    config: GameConfig,
    *,
    now_ms: int,
) -> LobbyTransition:
    _require_pre_match(room)
    actor_id = (
        actor_player_id
        if isinstance(actor_player_id, PlayerId)
        else PlayerId(actor_player_id)
    )
    _require_host(_player(room, actor_id))
    if not isinstance(config, GameConfig):
        raise TypeError("config must be a GameConfig")
    state = _next_state(room, config=config, now_ms=now_ms, clear_ready=True)
    return LobbyTransition(state=state, event_type="configUpdated", event_details={})


def authorize_lobby_config(
    room: RoomState, actor_player_id: PlayerId | str
) -> None:
    """Validate config mutation authority before parsing proposal contents."""

    _require_pre_match(room)
    actor_id = (
        actor_player_id
        if isinstance(actor_player_id, PlayerId)
        else PlayerId(actor_player_id)
    )
    _require_host(_player(room, actor_id))


def expire_disconnected_lobby_player(
    room: RoomState,
    player_id: PlayerId | str,
    *,
    now_ms: int,
) -> LobbyTransition:
    """Remove one timed-out human using the ordinary leave transition rules."""

    _require_pre_match(room)
    _require_timestamp(now_ms)
    target_id = player_id if isinstance(player_id, PlayerId) else PlayerId(player_id)
    _player(room, target_id)
    return _remove_human(
        room,
        target_id,
        target_id,
        now_ms=now_ms,
        event="playerLeft",
    )


def apply_lobby_disconnect(
    room: RoomState,
    player_id: PlayerId | str,
    connected_player_ids: Set[PlayerId | str],
    *,
    now_ms: int,
) -> LobbyTransition | None:
    """Reset readiness and transfer a disconnected host when possible."""

    _require_pre_match(room)
    _require_timestamp(now_ms)
    actor_id = player_id if isinstance(player_id, PlayerId) else PlayerId(player_id)
    actor = _player(room, actor_id)
    connected = {PlayerId(value) for value in connected_player_ids}
    successor = (
        _select_host_successor(
            room.players,
            excluded_player_id=actor_id,
            eligible_player_ids=connected,
        )
        if actor.role is PlayerRole.HOST
        else None
    )

    readiness_changed = actor.ready
    if not readiness_changed and successor is None:
        return None

    players = tuple(
        player.model_copy(
            update={
                "ready": False if player.player_id == actor_id else player.ready,
                "role": (
                    PlayerRole.HOST
                    if successor is not None
                    and player.player_id == successor.player_id
                    else PlayerRole.MEMBER
                    if successor is not None and player.player_id == actor_id
                    else player.role
                ),
            }
        )
        for player in room.players
    )
    state = _next_state(room, players=players, now_ms=now_ms, clear_ready=False)
    events: list[tuple[str, dict[str, object]]] = []
    if readiness_changed:
        events.append(
            ("playerReadinessChanged", {"playerId": str(actor_id), "ready": False})
        )
    if successor is not None:
        events.append(
            (
                "hostTransferred",
                {
                    "fromPlayerId": str(actor_id),
                    "toPlayerId": str(successor.player_id),
                },
            )
        )
    event_type, event_details = events[0]
    return LobbyTransition(
        state=state,
        event_type=event_type,
        event_details=event_details,
        additional_events=tuple(events[1:]),
    )


def reconcile_lobby_host(
    room: RoomState,
    connected_player_ids: Set[PlayerId | str],
    *,
    now_ms: int,
) -> LobbyTransition | None:
    """Transfer a disconnected host to the earliest connected human."""

    _require_pre_match(room)
    _require_timestamp(now_ms)
    connected = {PlayerId(value) for value in connected_player_ids}
    host = next(player for player in room.players if player.role is PlayerRole.HOST)
    if host.player_id in connected:
        return None
    successor = _select_host_successor(
        room.players,
        excluded_player_id=host.player_id,
        eligible_player_ids=connected,
    )
    if successor is None:
        return None
    players = tuple(
        player.model_copy(
            update={
                "ready": False if player.player_id == host.player_id else player.ready,
                "role": (
                    PlayerRole.HOST
                    if player.player_id == successor.player_id
                    else PlayerRole.MEMBER
                ),
            }
        )
        for player in room.players
    )
    state = _next_state(room, players=players, now_ms=now_ms, clear_ready=False)
    events: list[tuple[str, dict[str, object]]] = []
    if host.ready:
        events.append(
            ("playerReadinessChanged", {"playerId": str(host.player_id), "ready": False})
        )
    events.append(
        (
            "hostTransferred",
            {
                "fromPlayerId": str(host.player_id),
                "toPlayerId": str(successor.player_id),
            },
        )
    )
    event_type, event_details = events[0]
    return LobbyTransition(
        state=state,
        event_type=event_type,
        event_details=event_details,
        additional_events=tuple(events[1:]),
    )


def _remove_human(
    room: RoomState,
    actor_id: PlayerId,
    target_id: PlayerId,
    *,
    now_ms: int,
    event: str,
) -> LobbyTransition:
    target = _player(room, target_id)
    remaining = [player for player in room.players if player.player_id != target_id]
    target_seat = next(
        seat
        for seat in room.seats
        if isinstance(seat.controller, ExternalSeatController)
        and seat.controller.player_id == target_id
    )
    seats = tuple(
        SeatState(seat_id=seat.seat_id, slot=seat.slot)
        if seat.seat_id == target_seat.seat_id
        else seat
        for seat in room.seats
    )
    details: dict[str, object] = {
        "playerId": str(target_id),
        "seatId": str(target_seat.seat_id),
    }
    additional_events: tuple[tuple[str, dict[str, object]], ...] = ()
    if not remaining:
        state = _next_state(
            room,
            players=(),
            seats=seats,
            now_ms=now_ms,
            status=RoomStatus.FINISHED,
            clear_ready=False,
        )
    else:
        if target.role is PlayerRole.HOST:
            successor = _select_host_successor(tuple(remaining))
            if successor is None:  # pragma: no cover - guarded by ``remaining``
                raise AssertionError("remaining lobby players require a host")
            details["newHostPlayerId"] = str(successor.player_id)
            additional_events = (
                (
                    "hostTransferred",
                    {
                        "fromPlayerId": str(target_id),
                        "toPlayerId": str(successor.player_id),
                    },
                ),
            )
            remaining = [
                player.model_copy(
                    update={
                        "role": (
                            PlayerRole.HOST
                            if player.player_id == successor.player_id
                            else PlayerRole.MEMBER
                        ),
                        "ready": False,
                    }
                )
                for player in remaining
            ]
        state = _next_state(
            room,
            players=tuple(remaining),
            seats=seats,
            now_ms=now_ms,
            clear_ready=True,
        )
    return LobbyTransition(
        state=state,
        event_type=event,
        event_details=details,
        additional_events=additional_events,
        session_ended=actor_id == target.player_id,
    )


def _select_host_successor(
    players: tuple[PlayerState, ...] | list[PlayerState],
    *,
    excluded_player_id: PlayerId | None = None,
    eligible_player_ids: set[PlayerId] | None = None,
) -> PlayerState | None:
    candidates = tuple(
        player
        for player in players
        if player.player_id != excluded_player_id
        and (eligible_player_ids is None or player.player_id in eligible_player_ids)
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda player: (player.joined_at_ms, str(player.player_id)),
    )


def _next_state(
    room: RoomState,
    *,
    players: tuple[PlayerState, ...] | None = None,
    seats: tuple[SeatState, ...] | None = None,
    config: GameConfig | None = None,
    match: MatchState | None = None,
    status: RoomStatus | None = None,
    now_ms: int,
    clear_ready: bool = True,
) -> RoomState:
    next_players = room.players if players is None else players
    if clear_ready:
        next_players = tuple(
            player.model_copy(update={"ready": False}) for player in next_players
        )
    next_seats = room.seats if seats is None else seats
    next_status = status or _waiting_status(next_players, next_seats)
    values = room.model_dump()
    values.update(
        revision=room.revision + 1,
        players=next_players,
        seats=next_seats,
        config=room.config if config is None else config,
        match=match,
        status=next_status,
        updated_at_ms=max(now_ms, room.updated_at_ms),
    )
    return RoomState.model_validate(values)


def _same_revision_state(
    room: RoomState,
    *,
    players: tuple[PlayerState, ...],
    seats: tuple[SeatState, ...] | None = None,
) -> RoomState:
    values = room.model_dump()
    values.update(players=players, seats=room.seats if seats is None else seats)
    values["status"] = _waiting_status(values["players"], values["seats"])
    return RoomState.model_validate(values)


def _waiting_status(
    players: tuple[PlayerState, ...], seats: tuple[SeatState, ...]
) -> RoomStatus:
    if all(seat.controller is not None for seat in seats) and all(
        player.ready for player in players
    ):
        return RoomStatus.READY
    return RoomStatus.WAITING_FOR_PLAYERS


def _require_pre_match(room: RoomState) -> None:
    if room.status not in {
        RoomStatus.CREATED,
        RoomStatus.WAITING_FOR_PLAYERS,
        RoomStatus.READY,
    }:
        raise LobbyDomainError("ROOM_CLOSED", "room roster is frozen")


def _player(room: RoomState, player_id: PlayerId) -> PlayerState:
    player = next(
        (value for value in room.players if value.player_id == player_id), None
    )
    if player is None:
        raise LobbyDomainError("PLAYER_NOT_FOUND", "player is not in this room")
    return player


def _require_host(player: PlayerState) -> None:
    if player.role is not PlayerRole.HOST:
        raise LobbyDomainError("HOST_REQUIRED", "host permission is required")


def _require_unique_name(room: RoomState, name: str) -> None:
    if _name_key(name) in {_name_key(value) for value in _occupant_names(room)}:
        raise LobbyDomainError("DISPLAY_NAME_TAKEN", "display name is already in use")


def _occupant_names(room: RoomState) -> tuple[str, ...]:
    return tuple(
        seat.occupant_name for seat in room.seats if seat.occupant_name is not None
    )


def _name_key(value: str) -> str:
    return normalize_display_name(value).casefold()


def _sorted_seats(room: RoomState) -> tuple[SeatState, ...]:
    return tuple(sorted(room.seats, key=lambda seat: seat.slot))


def _require_timestamp(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("now_ms must be a non-negative integer")


__all__ = [
    "apply_lobby_disconnect",
    "authorize_lobby_config",
    "create_lobby_room",
    "expire_disconnected_lobby_player",
    "join_lobby_room",
    "normalize_display_name",
    "reconcile_lobby_host",
    "update_lobby_config",
]
