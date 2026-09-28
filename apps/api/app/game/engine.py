"""Shared game setup, transitions, and state helpers."""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol

from .actions import DomainAction
from .base import GameModel
from .capabilities import RoomCapability
from .effects import (
    DomainEffect,
)
from .events import (
    BonusExposed,
    DomainEvent,
    HandSetupCompleted,
    TileDrawn,
)
from .model import (
    AutomatedSeatController,
    AwaitingDrawPhase,
    CompletePhase,
    HandId,
    HandOutcome,
    HandResult,
    HandState,
    MatchResult,
    MatchState,
    MatchStatus,
    PhysicalTile,
    PlayerHand,
    PlayerId,
    RoomState,
    RoomStatus,
    SeatId,
    WallState,
    Wind,
    WindowId,
)
from .observation import PlayerObservation
from .projection import OpaqueActionDescriptor, PublicRoomView
from .runtime import RandomSource, SystemRandomSource
from .tiles import (
    canonical_physical_deck,
    is_bonus_tile,
    sort_playable_tiles,
)


MAX_AUTOMATED_CONTINUATIONS = 32


class IllegalGameActionError(ValueError):
    """Generic legal-action rejection that discloses no hidden state."""

    code = "ACTION_NOT_AVAILABLE"

    def __init__(self) -> None:
        super().__init__("action is not available")


class InvalidGameStateError(ValueError):
    pass


class TransitionResult(GameModel):
    state: RoomState
    domain_events: tuple[DomainEvent, ...] = ()
    effects: tuple[DomainEffect, ...] = ()


class GameEngine(Protocol):
    capabilities: tuple[RoomCapability, ...]

    def setup_match(self, state: RoomState) -> TransitionResult: ...

    def transition(
        self, state: RoomState, action: DomainAction
    ) -> TransitionResult: ...

    def legal_actions(
        self, state: RoomState, seat_id: SeatId
    ) -> tuple[DomainAction, ...]: ...

    def resolve_discard_window(
        self, state: RoomState, window_id: WindowId
    ) -> TransitionResult: ...


class ObservationBuilder(Protocol):
    def __call__(
        self,
        room: RoomState,
        viewer_player_id: PlayerId,
        *,
        capabilities: tuple[RoomCapability, ...] | None = None,
    ) -> PlayerObservation: ...


class ProjectionBuilder(Protocol):
    def __call__(
        self,
        room: RoomState,
        viewer_player_id: PlayerId,
        *,
        server_time_ms: int,
        capabilities: tuple[RoomCapability, ...] | None = None,
        actions: tuple[OpaqueActionDescriptor, ...] = (),
        **kwargs: object,
    ) -> PublicRoomView: ...


class _GameSetup:
    """Shared match setup for the Singapore game engine."""

    def __init__(self, rng: RandomSource | None = None) -> None:
        self._rng = SystemRandomSource() if rng is None else rng

    def setup_match(self, state: RoomState) -> TransitionResult:
        self._require(state)
        if (
            state.status is not RoomStatus.IN_MATCH
            or state.match is None
            or state.match.status is not MatchStatus.PENDING_SETUP
            or state.pending_deadline is not None
        ):
            raise InvalidGameStateError("match is not awaiting setup")

        seats = tuple(sorted(state.seats, key=lambda seat: seat.slot))
        if any(seat.controller is None for seat in seats):
            raise InvalidGameStateError("setup requires four occupied seats")
        dealer_index = self._rng.randbelow(len(seats))
        if type(dealer_index) is not int or not 0 <= dealer_index < len(seats):
            raise InvalidGameStateError("random source returned an invalid dealer")
        dealer_seat_id = seats[dealer_index].seat_id
        deal_order = (*seats[dealer_index:], *seats[:dealer_index])
        hand_id = _first_hand_id(state)

        canonical_deck = canonical_physical_deck(hand_id)
        shuffled = self._rng.shuffled(canonical_deck)
        if len(shuffled) != 148 or set(shuffled) != set(canonical_deck):
            raise InvalidGameStateError(
                "random source did not return a deck permutation"
            )
        salt_value = self._rng.randbelow(1 << 256)
        if type(salt_value) is not int or not 0 <= salt_value < (1 << 256):
            raise InvalidGameStateError("random source returned invalid tile entropy")
        tile_id_salt = f"{salt_value:064x}"
        shuffled = _opaque_physical_deck(
            hand_id,
            tile_id_salt,
            shuffled,
        )
        live = list(shuffled[:133])
        reserve = list(shuffled[133:])

        raw_by_seat: dict[SeatId, list[PhysicalTile]] = {
            seat.seat_id: [] for seat in seats
        }
        for _ in range(13):
            for seat in deal_order:
                raw_by_seat[seat.seat_id].append(live.pop(0))

        setup_events: list[DomainEvent] = [HandSetupCompleted(hand_id=hand_id)]
        player_hands: list[PlayerHand] = []
        for seat in deal_order:
            concealed: list[PhysicalTile] = []
            bonus: list[PhysicalTile] = []
            raw = tuple(raw_by_seat[seat.seat_id])
            for tile in raw:
                if is_bonus_tile(tile):
                    bonus.append(tile)
                    setup_events.append(
                        BonusExposed(
                            seat_id=seat.seat_id,
                            tile=tile,
                            initial=True,
                        )
                    )
                    replacement = _replacement_chain(
                        seat.seat_id,
                        live,
                        reserve,
                        bonus,
                        setup_events,
                        maximum_steps=len(canonical_deck),
                    )
                    if replacement is None:
                        raise InvalidGameStateError(
                            "live wall ended during initial replacement"
                        )
                    concealed.append(replacement)
                else:
                    concealed.append(tile)
            player_hands.append(
                PlayerHand(
                    seat_id=seat.seat_id,
                    concealed_tiles=sort_playable_tiles(concealed),
                    bonus_tiles=tuple(bonus),
                    initial_tile_ids=tuple(tile.tile_id for tile in raw),
                )
            )

        hands_by_seat = {hand.seat_id: hand for hand in player_hands}
        ordered_hands = tuple(hands_by_seat[seat.seat_id] for seat in seats)
        hand = HandState(
            hand_id=hand_id,
            tile_id_salt=tile_id_salt,
            phase=AwaitingDrawPhase(seat_id=dealer_seat_id),
            wall=WallState(
                live_tiles=tuple(live),
                reserve_tiles=tuple(reserve),
            ),
            player_hands=ordered_hands,
        )
        match = MatchState(
            match_id=state.match.match_id,
            status=MatchStatus.ACTIVE,
            prevailing_wind=Wind.EAST,
            dealer_seat_id=dealer_seat_id,
            current_hand=hand,
            hand_history=state.match.hand_history,
            balances=state.match.balances,
        )
        setup_state = _rebuild_room(state, match=match, pending_deadline=None)
        drawn = self._automatic_draw(setup_state, dealer_seat_id)
        result = TransitionResult(
            state=drawn.state,
            domain_events=(*setup_events, *drawn.domain_events),
            effects=drawn.effects,
        )
        self._validate(result.state)
        return result


def _replacement_chain(
    seat_id: SeatId,
    live: list[PhysicalTile],
    reserve: list[PhysicalTile],
    bonus: list[PhysicalTile],
    events: list[DomainEvent],
    *,
    maximum_steps: int = MAX_AUTOMATED_CONTINUATIONS,
) -> PhysicalTile | None:
    """Draw opposite-end replacements while preserving a 15-tile reserve."""

    steps = 0
    maximum_steps = min(maximum_steps, len(live))
    while live:
        if steps >= maximum_steps:
            raise InvalidGameStateError("replacement continuation exceeded its guard")
        steps += 1
        if len(reserve) != 15:
            raise InvalidGameStateError("replacement reserve must contain 15 tiles")
        replacement = reserve.pop()
        reserve.insert(0, live.pop())
        events.append(TileDrawn(seat_id=seat_id, tile=replacement, replacement=True))
        if not is_bonus_tile(replacement):
            return replacement
        bonus.append(replacement)
        events.append(BonusExposed(seat_id=seat_id, tile=replacement, initial=False))
    return None


def _complete_tie(state: RoomState, hand: HandState) -> RoomState:
    complete = HandState(
        hand_id=hand.hand_id,
        tile_id_salt=hand.tile_id_salt,
        phase=CompletePhase(),
        wall=hand.wall,
        player_hands=hand.player_hands,
        discards=hand.discards,
        pending_claims=(),
        payments=hand.payments,
        result=HandResult(
            outcome=HandOutcome.TIE,
            reason="LIVE_WALL_EXHAUSTED",
        ),
    )
    return _room_with_hand(state, complete, pending_deadline=None)


def finalize_completed_preview(state: RoomState, *, completed_at_ms: int) -> RoomState:
    """Finalize a clock-free completed hand using room-sampled time."""

    from .singapore_game import validate_room as validator
    if (
        not isinstance(completed_at_ms, int)
        or isinstance(completed_at_ms, bool)
        or completed_at_ms < 0
    ):
        raise ValueError("completed_at_ms must be a non-negative integer")
    if state.status is RoomStatus.FINISHED:
        validator(state, require_deadline=True)
        return state
    validator(state)
    if (
        state.match is None
        or state.match.status is not MatchStatus.ACTIVE
        or state.match.current_hand is None
        or not isinstance(state.match.current_hand.phase, CompletePhase)
        or state.match.current_hand.result is None
    ):
        raise InvalidGameStateError("preview hand is not complete")

    hand = state.match.current_hand
    history = state.match.hand_history
    if not history or history[-1] != hand.result:
        history = (*history, hand.result)
    winner_ids = (
        () if hand.result.winner_seat_id is None else (hand.result.winner_seat_id,)
    )
    match = MatchState(
        match_id=state.match.match_id,
        status=MatchStatus.FINISHED,
        prevailing_wind=state.match.prevailing_wind,
        dealer_seat_id=state.match.dealer_seat_id,
        current_hand=hand,
        hand_history=history,
        balances=state.match.balances,
        result=MatchResult(
            final_balances=state.match.balances,
            winning_seat_ids=winner_ids,
            completed_at_ms=completed_at_ms,
            reason=hand.result.reason,
        ),
    )
    finalized = _rebuild_room(
        state,
        status=RoomStatus.FINISHED,
        match=match,
        pending_deadline=None,
    )
    validator(finalized, require_deadline=True)
    return finalized


def _validate_tie_result(result: HandResult) -> None:
    if (
        result.outcome is not HandOutcome.TIE
        or result.reason != "LIVE_WALL_EXHAUSTED"
        or result.winner_seat_id is not None
        or result.provider_seat_id is not None
        or result.win_source is not None
        or result.fan != 0
        or result.fan_awards
        or result.payments
    ):
        raise InvalidGameStateError("hand result must be an unscored wall tie")


def _first_hand_id(state: RoomState) -> HandId:
    if state.match is None:
        raise InvalidGameStateError("room has no match")
    digest = hashlib.sha256(
        f"zimo:hand:v1:{state.match.match_id}:1".encode()
    ).hexdigest()[:32]
    return HandId(f"hand_{digest}")


def _opaque_physical_deck(
    hand_id: HandId,
    tile_id_salt: str,
    tiles: tuple[PhysicalTile, ...] | None = None,
) -> tuple[PhysicalTile, ...]:
    """Relabel canonical tiles with state-secret, non-enumerable identifiers."""

    try:
        key = bytes.fromhex(tile_id_salt)
    except ValueError as exc:
        raise InvalidGameStateError("tile identity salt is invalid") from exc
    if len(key) != 32:
        raise InvalidGameStateError("tile identity salt is invalid")
    source = canonical_physical_deck(hand_id) if tiles is None else tiles
    return tuple(
        PhysicalTile(
            tile_id=type(tile.tile_id)(
                "tile_"
                + hmac.new(
                    key,
                    f"zimo:physical-tile:v1:{tile.tile_id}".encode(),
                    hashlib.sha256,
                ).hexdigest()
            ),
            face=tile.face,
        )
        for tile in source
    )


def _discard_window_id(hand_id: HandId, sequence: int) -> WindowId:
    digest = hashlib.sha256(
        f"zimo:discard-window:v1:{hand_id}:{sequence}".encode()
    ).hexdigest()[:32]
    return WindowId(f"window_{digest}")


def _player_hand(hand: HandState, seat_id: SeatId) -> PlayerHand:
    try:
        return next(value for value in hand.player_hands if value.seat_id == seat_id)
    except StopIteration as exc:
        raise InvalidGameStateError("hand does not contain the requested seat") from exc


def _replace_player_hand(
    hand: HandState, replacement: PlayerHand
) -> tuple[PlayerHand, ...]:
    return tuple(
        replacement if value.seat_id == replacement.seat_id else value
        for value in hand.player_hands
    )


def _is_automated(state: RoomState, seat_id: SeatId) -> bool:
    seat = next(value for value in state.seats if value.seat_id == seat_id)
    return isinstance(seat.controller, AutomatedSeatController)


def _room_with_hand(
    state: RoomState,
    hand: HandState,
    *,
    pending_deadline: object,
) -> RoomState:
    if state.match is None:
        raise InvalidGameStateError("room has no match")
    match_data = state.match.model_dump()
    match_data["current_hand"] = hand
    match = MatchState.model_validate(match_data)
    return _rebuild_room(
        state,
        match=match,
        pending_deadline=pending_deadline,
    )


_UNCHANGED = object()


def _rebuild_room(
    state: RoomState,
    *,
    status: RoomStatus | object = _UNCHANGED,
    match: MatchState | object = _UNCHANGED,
    pending_deadline: object = _UNCHANGED,
) -> RoomState:
    values = state.model_dump()
    if status is not _UNCHANGED:
        values["status"] = status
    if match is not _UNCHANGED:
        values["match"] = match
    if pending_deadline is not _UNCHANGED:
        values["pending_deadline"] = pending_deadline
    return RoomState.model_validate(values)


def transition(state: RoomState, action: DomainAction) -> TransitionResult:
    from .singapore_game import SingaporeGameEngine

    return SingaporeGameEngine().transition(state, action)


def legal_actions(state: RoomState, seat_id: SeatId) -> tuple[DomainAction, ...]:
    from .singapore_game import SingaporeGameEngine

    return SingaporeGameEngine().legal_actions(state, seat_id)


__all__ = [
    "GameEngine", "IllegalGameActionError", "InvalidGameStateError",
    "MAX_AUTOMATED_CONTINUATIONS", "ObservationBuilder", "ProjectionBuilder",
    "TransitionResult", "finalize_completed_preview", "legal_actions", "transition",
]
