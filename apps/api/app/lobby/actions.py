"""Pure lobby action catalogue, resolution, and application."""

from __future__ import annotations

import hashlib
import json

if "." in (__package__ or ""):
    from ..game import (
        AutomatedSeatController,
        MatchId,
        MatchState,
        MatchStatus,
        OpaqueActionDescriptor,
        PlayerId,
        PlayerRole,
        RoomState,
        RoomStatus,
        SeatBalance,
        SeatId,
        SeatState,
    )
else:  # pragma: no cover - Pyodide Worker module loading
    from game import (
        AutomatedSeatController,
        MatchId,
        MatchState,
        MatchStatus,
        OpaqueActionDescriptor,
        PlayerId,
        PlayerRole,
        RoomState,
        RoomStatus,
        SeatBalance,
        SeatId,
        SeatState,
    )

from .state import (
    _name_key,
    _next_state,
    _occupant_names,
    _player,
    _remove_human,
    _require_host,
    _require_pre_match,
    _require_timestamp,
    _same_revision_state,
    _sorted_seats,
)
from .types import (
    CataloguedLobbyAction,
    LobbyAction,
    LobbyActionKind,
    LobbyDomainError,
    LobbyTransition,
    RANDOM_BOT_POLICY_ID,
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
                kind=(
                    LobbyActionKind.UNREADY
                    if player.ready
                    else LobbyActionKind.READY
                )
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

    connection_required = {
        LobbyActionKind.READY,
        LobbyActionKind.START_MATCH,
        LobbyActionKind.START_AGAINST_BOTS,
    }
    return tuple(
        CataloguedLobbyAction(
            descriptor=OpaqueActionDescriptor(
                action_id=_action_id(room, player_id, action),
                label=label,
                enabled=viewer_connected or action.kind not in connection_required,
                tone=tone,  # type: ignore[arg-type]
                disabled_reason=(
                    None
                    if viewer_connected or action.kind not in connection_required
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
                raise LobbyDomainError("ACTION_NOT_AVAILABLE", "action is not available")
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
                ("playerReadinessChanged", {"playerId": str(actor_id), "ready": True}),
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
            players=tuple(
                player.model_copy(update={"ready": False}) for player in room.players
            ),
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


__all__ = [
    "apply_lobby_action",
    "catalog_lobby_actions",
    "resolve_lobby_action",
]
