"""Pure Milestone 2 lobby policy and transitions.

The module deliberately knows nothing about HTTP, credentials, SQL, clocks, or
WebSockets.  Callers supply identities and timestamps, then persist the returned
canonical state before exposing it.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Set
from dataclasses import dataclass
from enum import StrEnum

if __package__:
    from .game import (
        AutomatedSeatController,
        ExternalSeatController,
        GameConfig,
        GameModel,
        MatchId,
        MatchState,
        MatchStatus,
        OpaqueActionDescriptor,
        PlayerId,
        PlayerRole,
        PlayerState,
        PolicyId,
        RoomId,
        RoomState,
        RoomStatus,
        SeatBalance,
        SeatId,
        SeatState,
        standard_seats,
    )
else:  # pragma: no cover - Pyodide Worker module loading
    from game import (
        AutomatedSeatController,
        ExternalSeatController,
        GameConfig,
        GameModel,
        MatchId,
        MatchState,
        MatchStatus,
        OpaqueActionDescriptor,
        PlayerId,
        PlayerRole,
        PlayerState,
        PolicyId,
        RoomId,
        RoomState,
        RoomStatus,
        SeatBalance,
        SeatId,
        SeatState,
        standard_seats,
    )


RANDOM_BOT_POLICY_ID = PolicyId("randomBot")
MAX_DISPLAY_NAME_LENGTH = 64


class LobbyDomainError(ValueError):
    """Expected pure-domain rejection with a stable transport-neutral code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class LobbyActionKind(StrEnum):
    READY = "ready"
    UNREADY = "unready"
    ADD_BOT = "addBot"
    FILL_BOTS = "fillBots"
    REMOVE_BOT = "removeBot"
    REMOVE_PLAYER = "removePlayer"
    LEAVE = "leave"
    ROTATE_INVITE = "rotateInvite"
    START_MATCH = "startMatch"
    START_AGAINST_BOTS = "startAgainstBots"


class LobbyAction(GameModel):
    kind: LobbyActionKind
    target_seat_id: SeatId | None = None
    target_player_id: PlayerId | None = None


@dataclass(frozen=True, slots=True)
class CataloguedLobbyAction:
    descriptor: OpaqueActionDescriptor
    action: LobbyAction


@dataclass(frozen=True, slots=True)
class LobbyTransition:
    state: RoomState
    event_type: str
    event_details: dict[str, object]
    additional_events: tuple[tuple[str, dict[str, object]], ...] = ()
    rotate_invite: bool = False
    session_ended: bool = False


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

    joined_at_ms = max(
        now_ms,
        room.updated_at_ms,
    )
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


def catalog_lobby_actions(
    room: RoomState,
    viewer_player_id: PlayerId | str,
    *,
    viewer_connected: bool = True,
) -> tuple[CataloguedLobbyAction, ...]:
    player_id = (
        viewer_player_id
        if isinstance(viewer_player_id, PlayerId)
        else PlayerId(viewer_player_id)
    )
    player = _player(room, player_id)
    if room.status not in {
        RoomStatus.CREATED,
        RoomStatus.WAITING_FOR_PLAYERS,
        RoomStatus.READY,
    }:
        return ()

    actions: list[tuple[LobbyAction, str, str]] = []
    actions.append(
        (
            LobbyAction(
                kind=LobbyActionKind.UNREADY
                if player.ready
                else LobbyActionKind.READY
            ),
            "Unready" if player.ready else "Ready",
            "neutral" if player.ready else "primary",
        )
    )
    empty_seats = [seat for seat in _sorted_seats(room) if seat.controller is None]
    if player.role is PlayerRole.HOST:
        if empty_seats:
            actions.append((LobbyAction(kind=LobbyActionKind.ADD_BOT), "Add Bot", "neutral"))
            actions.append(
                (
                    LobbyAction(kind=LobbyActionKind.FILL_BOTS),
                    "Fill Open Seats With Bots",
                    "neutral",
                )
            )
        for seat in _sorted_seats(room):
            if isinstance(seat.controller, AutomatedSeatController):
                actions.append(
                    (
                        LobbyAction(
                            kind=LobbyActionKind.REMOVE_BOT,
                            target_seat_id=seat.seat_id,
                        ),
                        f"Remove Bot {seat.occupant_name}",
                        "danger",
                    )
                )
        for member in sorted(
            (value for value in room.players if value.player_id != player_id),
            key=lambda value: (value.joined_at_ms, str(value.player_id)),
        ):
            actions.append(
                (
                    LobbyAction(
                        kind=LobbyActionKind.REMOVE_PLAYER,
                        target_player_id=member.player_id,
                    ),
                    f"Remove Player {member.display_name}",
                    "danger",
                )
            )
        actions.append(
            (
                LobbyAction(kind=LobbyActionKind.ROTATE_INVITE),
                "Create New Invitation Link",
                "neutral",
            )
        )
        if _can_start(room):
            actions.append(
                (LobbyAction(kind=LobbyActionKind.START_MATCH), "Start Match", "primary")
            )
        if len(room.players) == 1:
            actions.append(
                (
                    LobbyAction(kind=LobbyActionKind.START_AGAINST_BOTS),
                    "Start Against Bots",
                    "primary",
                )
            )
    actions.append((LobbyAction(kind=LobbyActionKind.LEAVE), "Leave Room", "danger"))

    return tuple(
        CataloguedLobbyAction(
            descriptor=OpaqueActionDescriptor(
                action_id=_action_id(room, player_id, action),
                label=label,
                enabled=(
                    viewer_connected
                    or action.kind
                    not in {
                        LobbyActionKind.READY,
                        LobbyActionKind.START_MATCH,
                        LobbyActionKind.START_AGAINST_BOTS,
                    }
                ),
                tone=tone,  # type: ignore[arg-type]
                disabled_reason=(
                    None
                    if viewer_connected
                    or action.kind
                    not in {
                        LobbyActionKind.READY,
                        LobbyActionKind.START_MATCH,
                        LobbyActionKind.START_AGAINST_BOTS,
                    }
                    else "Reconnect before getting ready."
                    if action.kind is LobbyActionKind.READY
                    else "Reconnect before starting."
                ),
                presentation_slot=(
                    "invitation"
                    if action.kind is LobbyActionKind.ROTATE_INVITE
                    else "roomActions"
                ),
            ),
            action=action,
        )
        for action, label, tone in actions
    )


def resolve_lobby_action(
    room: RoomState,
    viewer_player_id: PlayerId | str,
    action_id: str,
    *,
    viewer_connected: bool = True,
) -> LobbyAction:
    if not isinstance(action_id, str) or not action_id:
        raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
    for item in catalog_lobby_actions(
        room,
        viewer_player_id,
        viewer_connected=viewer_connected,
    ):
        if item.descriptor.action_id == action_id:
            if not item.descriptor.enabled:
                raise LobbyDomainError(
                    "ACTION_NOT_AVAILABLE", "action is not available"
                )
            return item.action
    raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")


def apply_lobby_action(
    room: RoomState,
    actor_player_id: PlayerId | str,
    action: LobbyAction,
    *,
    now_ms: int,
    match_id: MatchId | str | None = None,
) -> LobbyTransition:
    _require_pre_match(room)
    _require_timestamp(now_ms)
    actor_id = (
        actor_player_id
        if isinstance(actor_player_id, PlayerId)
        else PlayerId(actor_player_id)
    )
    actor = _player(room, actor_id)

    if action.kind in {LobbyActionKind.READY, LobbyActionKind.UNREADY}:
        ready = action.kind is LobbyActionKind.READY
        if actor.ready == ready:
            raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
        players = tuple(
            player.model_copy(update={"ready": ready})
            if player.player_id == actor_id
            else player
            for player in room.players
        )
        state = _next_state(room, players=players, now_ms=now_ms, clear_ready=False)
        return LobbyTransition(
            state=state,
            event_type="playerReadinessChanged",
            event_details={"playerId": str(actor_id), "ready": ready},
        )

    if action.kind is LobbyActionKind.LEAVE:
        return _remove_human(room, actor_id, actor_id, now_ms=now_ms, event="playerLeft")

    _require_host(actor)
    if action.kind is LobbyActionKind.ADD_BOT:
        empty = next((seat for seat in _sorted_seats(room) if seat.controller is None), None)
        if empty is None:
            raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
        state, added = _add_bots(room, (empty.seat_id,), now_ms=now_ms)
        return LobbyTransition(
            state=state,
            event_type="botAdded",
            event_details={"seatId": str(empty.seat_id), "displayName": added[0]},
        )

    if action.kind is LobbyActionKind.FILL_BOTS:
        empty_ids = tuple(
            seat.seat_id for seat in _sorted_seats(room) if seat.controller is None
        )
        if not empty_ids:
            raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
        state, added = _add_bots(room, empty_ids, now_ms=now_ms)
        return LobbyTransition(
            state=state,
            event_type="botsFilled",
            event_details={"count": len(added)},
        )

    if action.kind is LobbyActionKind.REMOVE_BOT:
        target = action.target_seat_id
        seat = next((seat for seat in room.seats if seat.seat_id == target), None)
        if seat is None or not isinstance(seat.controller, AutomatedSeatController):
            raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
        seats = tuple(
            SeatState(seat_id=value.seat_id, slot=value.slot)
            if value.seat_id == target
            else value
            for value in room.seats
        )
        state = _next_state(room, seats=seats, now_ms=now_ms)
        return LobbyTransition(
            state=state,
            event_type="botRemoved",
            event_details={"seatId": str(target)},
        )

    if action.kind is LobbyActionKind.REMOVE_PLAYER:
        target = action.target_player_id
        if target is None or target == actor_id:
            raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
        return _remove_human(room, actor_id, target, now_ms=now_ms, event="playerRemoved")

    if action.kind is LobbyActionKind.ROTATE_INVITE:
        state = _next_state(room, now_ms=now_ms, clear_ready=False)
        return LobbyTransition(
            state=state,
            event_type="inviteRotated",
            event_details={},
            rotate_invite=True,
        )

    if action.kind is LobbyActionKind.START_MATCH:
        if not _can_start(room):
            raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
        return _start(room, now_ms=now_ms, match_id=match_id)

    if action.kind is LobbyActionKind.START_AGAINST_BOTS:
        if len(room.players) != 1:
            raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
        empty_ids = tuple(
            seat.seat_id for seat in _sorted_seats(room) if seat.controller is None
        )
        filled = room
        filled_count = len(empty_ids)
        if empty_ids:
            filled, _ = _add_bots(room, empty_ids, now_ms=now_ms, advance=False)
        players = tuple(player.model_copy(update={"ready": True}) for player in filled.players)
        filled = _same_revision_state(filled, players=players)
        started = _start(filled, now_ms=now_ms, match_id=match_id, previous=room)
        events: list[tuple[str, dict[str, object]]] = []
        if filled_count:
            events.append(("botsFilled", {"count": filled_count}))
        events.extend(
            (
                (
                    "playerReadinessChanged",
                    {"playerId": str(actor_id), "ready": True},
                ),
                (started.event_type, started.event_details),
            )
        )
        first_type, first_details = events[0]
        return LobbyTransition(
            state=started.state,
            event_type=first_type,
            event_details=first_details,
            additional_events=tuple(events[1:]),
        )

    raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")


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
    """Apply the canonical pre-match consequences of a final-socket close.

    Presence itself remains outside ``RoomState``.  This transition only resets
    the disconnecting human's readiness and, when that human is host, transfers
    host permission to the earliest-joined human who is currently connected.
    """

    _require_pre_match(room)
    _require_timestamp(now_ms)
    actor_id = player_id if isinstance(player_id, PlayerId) else PlayerId(player_id)
    actor = _player(room, actor_id)
    connected = {PlayerId(value) for value in connected_player_ids}
    successor = None
    if actor.role is PlayerRole.HOST:
        candidates = tuple(
            player
            for player in room.players
            if player.player_id != actor_id and player.player_id in connected
        )
        if candidates:
            successor = min(
                candidates,
                key=lambda player: (player.joined_at_ms, str(player.player_id)),
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
    state = _next_state(
        room,
        players=players,
        now_ms=now_ms,
        clear_ready=False,
    )
    events: list[tuple[str, dict[str, object]]] = []
    if readiness_changed:
        events.append(
            (
                "playerReadinessChanged",
                {"playerId": str(actor_id), "ready": False},
            )
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
    candidates = tuple(
        player for player in room.players if player.player_id in connected
    )
    if not candidates:
        return None
    successor = min(
        candidates,
        key=lambda player: (player.joined_at_ms, str(player.player_id)),
    )
    players = tuple(
        player.model_copy(
            update={
                "ready": False if player.player_id == host.player_id else player.ready,
                "role": (
                    PlayerRole.HOST
                    if player.player_id == successor.player_id
                    else PlayerRole.MEMBER
                )
            }
        )
        for player in room.players
    )
    state = _next_state(
        room,
        players=players,
        now_ms=now_ms,
        clear_ready=False,
    )
    events: list[tuple[str, dict[str, object]]] = []
    if host.ready:
        events.append(
            (
                "playerReadinessChanged",
                {"playerId": str(host.player_id), "ready": False},
            )
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
            successor = min(
                remaining,
                key=lambda player: (
                    player.joined_at_ms,
                    str(player.player_id),
                ),
            )
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
                        "role": PlayerRole.HOST
                        if player.player_id == successor.player_id
                        else PlayerRole.MEMBER,
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


def _add_bots(
    room: RoomState,
    seat_ids: tuple[SeatId, ...],
    *,
    now_ms: int,
    advance: bool = True,
) -> tuple[RoomState, tuple[str, ...]]:
    existing_names = {_name_key(name) for name in _occupant_names(room)}
    names: list[str] = []
    next_number = 1
    for _ in seat_ids:
        while _name_key(f"Bot {next_number}") in existing_names:
            next_number += 1
        name = f"Bot {next_number}"
        names.append(name)
        existing_names.add(_name_key(name))
        next_number += 1
    by_seat = dict(zip(seat_ids, names, strict=True))
    seats = tuple(
        SeatState(
            seat_id=seat.seat_id,
            slot=seat.slot,
            controller=AutomatedSeatController(policy_id=RANDOM_BOT_POLICY_ID),
            occupant_name=by_seat[seat.seat_id],
        )
        if seat.seat_id in by_seat
        else seat
        for seat in room.seats
    )
    if advance:
        state = _next_state(room, seats=seats, now_ms=now_ms, clear_ready=True)
    else:
        state = _same_revision_state(
            room,
            seats=seats,
            players=tuple(player.model_copy(update={"ready": False}) for player in room.players),
        )
    return state, tuple(names)


def _start(
    room: RoomState,
    *,
    now_ms: int,
    match_id: MatchId | str | None,
    previous: RoomState | None = None,
) -> LobbyTransition:
    if any(seat.controller is None for seat in room.seats) or any(
        not player.ready for player in room.players
    ):
        raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
    if match_id is None:
        digest = hashlib.sha256(
            f"zimo:match:v1:{room.room_id}:{(previous or room).revision + 1}".encode()
        ).hexdigest()[:32]
        match_id = MatchId(f"match_{digest}")
    elif not isinstance(match_id, MatchId):
        match_id = MatchId(match_id)
    match = MatchState(
        match_id=match_id,
        status=MatchStatus.PENDING_SETUP,
        dealer_seat_id=None,
        current_hand=None,
        balances=tuple(
            SeatBalance(seat_id=seat.seat_id, points=0) for seat in _sorted_seats(room)
        ),
    )
    baseline = previous or room
    state = _next_state(
        baseline,
        players=room.players,
        seats=room.seats,
        match=match,
        status=RoomStatus.IN_MATCH,
        now_ms=now_ms,
        clear_ready=False,
    )
    return LobbyTransition(
        state=state,
        event_type="matchStarted",
        event_details={"matchId": str(match_id)},
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


def _can_start(room: RoomState) -> bool:
    return (
        room.status is RoomStatus.READY
        and all(seat.controller is not None for seat in room.seats)
        and bool(room.players)
        and all(player.ready for player in room.players)
    )


def _action_id(room: RoomState, player_id: PlayerId, action: LobbyAction) -> str:
    material = json.dumps(
        {
            "action": action.canonical_data(),
            "playerId": str(player_id),
            "revision": room.revision,
            "roomId": str(room.room_id),
            "version": 1,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(material).hexdigest()


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
        raise LobbyDomainError(
            "DISPLAY_NAME_TAKEN", "display name is already in use"
        )


def _occupant_names(room: RoomState) -> tuple[str, ...]:
    return tuple(
        seat.occupant_name
        for seat in room.seats
        if seat.occupant_name is not None
    )


def _name_key(value: str) -> str:
    return normalize_display_name(value).casefold()


def _sorted_seats(room: RoomState) -> tuple[SeatState, ...]:
    return tuple(sorted(room.seats, key=lambda seat: seat.slot))


def _require_timestamp(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("now_ms must be a non-negative integer")


__all__ = [
    "CataloguedLobbyAction",
    "LobbyAction",
    "LobbyActionKind",
    "LobbyDomainError",
    "LobbyTransition",
    "RANDOM_BOT_POLICY_ID",
    "apply_lobby_action",
    "authorize_lobby_config",
    "catalog_lobby_actions",
    "create_lobby_room",
    "join_lobby_room",
    "normalize_display_name",
    "resolve_lobby_action",
    "update_lobby_config",
]
