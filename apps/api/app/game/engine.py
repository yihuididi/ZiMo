"""Pure, clock-free Singapore draw/discard preview engine."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections import Counter
from typing import Protocol

from .actions import Discard, DomainAction
from .base import GameModel
from .capabilities import (
    MILESTONE_3_CAPABILITIES,
    MILESTONE_3_RULESET_VERSION,
    MILESTONE_3_STATE_SCHEMA_VERSION,
    RoomCapability,
)
from .effects import (
    AutomatedDecisionRequested,
    ClaimWindowRequested,
    DomainEffect,
    MatchCompletionRequested,
)
from .events import (
    BonusExposed,
    DiscardWindowResolved,
    DomainEvent,
    HandCompleted,
    HandSetupCompleted,
    TileDiscarded,
    TileDrawn,
)
from .model import (
    AutomatedSeatController,
    AwaitingDiscardPhase,
    AwaitingDrawPhase,
    CompletePhase,
    DiscardClaimsPhase,
    DiscardState,
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
    canonical_face_counts,
    canonical_physical_deck,
    is_bonus_tile,
    sort_playable_tiles,
)


MILESTONE_1_CAPABILITIES: tuple[()] = ()
MAX_AUTOMATED_CONTINUATIONS = 32


class GameplayUnavailableError(RuntimeError):
    """Typed rejection for a ruleset version without gameplay."""

    code = "GAMEPLAY_UNAVAILABLE"

    def __init__(self, action: DomainAction) -> None:
        self.action_type = action.type
        super().__init__(
            f"{self.code}: action {action.type!r} is not enabled by this ruleset"
        )


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


class MilestoneOneEngine:
    capabilities = MILESTONE_1_CAPABILITIES

    def setup_match(self, state: RoomState) -> TransitionResult:
        del state
        raise RuntimeError("gameplay setup is not enabled by ruleset 0.1.0")

    def transition(
        self, state: RoomState, action: DomainAction
    ) -> TransitionResult:
        del state
        raise GameplayUnavailableError(action)

    def legal_actions(
        self, state: RoomState, seat_id: SeatId
    ) -> tuple[DomainAction, ...]:
        del state, seat_id
        return ()

    def resolve_discard_window(
        self, state: RoomState, window_id: WindowId
    ) -> TransitionResult:
        del state, window_id
        raise RuntimeError("discard windows are not enabled by ruleset 0.1.0")


class MilestoneThreeEngine:
    """Automatic-draw preview whose only controller choice is a discard."""

    capabilities = MILESTONE_3_CAPABILITIES

    def __init__(self, rng: RandomSource | None = None) -> None:
        self._rng = SystemRandomSource() if rng is None else rng

    def setup_match(self, state: RoomState) -> TransitionResult:
        _require_milestone_three(state)
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
            raise InvalidGameStateError("random source did not return a deck permutation")
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
        validate_milestone_three_room(result.state)
        return result

    def legal_actions(
        self, state: RoomState, seat_id: SeatId
    ) -> tuple[DomainAction, ...]:
        _require_milestone_three(state)
        if state.match is None or state.match.current_hand is None:
            return ()
        hand = state.match.current_hand
        if (
            not isinstance(hand.phase, AwaitingDiscardPhase)
            or hand.phase.seat_id != seat_id
            or state.status is not RoomStatus.IN_MATCH
            or state.match.status is not MatchStatus.ACTIVE
        ):
            return ()
        player_hand = _player_hand(hand, seat_id)
        actions: list[DomainAction] = [
            Discard(seat_id=seat_id, tile_id=tile.tile_id)
            for tile in player_hand.concealed_tiles
        ]
        if player_hand.drawn_tile is not None:
            actions.append(
                Discard(seat_id=seat_id, tile_id=player_hand.drawn_tile.tile_id)
            )
        return tuple(actions)

    def transition(
        self, state: RoomState, action: DomainAction
    ) -> TransitionResult:
        _require_milestone_three(state)
        if not isinstance(action, Discard) or action not in self.legal_actions(
            state, action.seat_id
        ):
            raise IllegalGameActionError()
        if state.match is None or state.match.current_hand is None:
            raise IllegalGameActionError()
        hand = state.match.current_hand
        player_hand = _player_hand(hand, action.seat_id)
        drawn = player_hand.drawn_tile
        if drawn is None:
            raise InvalidGameStateError("discard phase is missing its drawn tile")

        if drawn.tile_id == action.tile_id:
            discarded = drawn
            concealed = player_hand.concealed_tiles
        else:
            selected = next(
                (
                    tile
                    for tile in player_hand.concealed_tiles
                    if tile.tile_id == action.tile_id
                ),
                None,
            )
            if selected is None:
                raise IllegalGameActionError()
            discarded = selected
            concealed = sort_playable_tiles(
                (
                    *(tile for tile in player_hand.concealed_tiles if tile != selected),
                    drawn,
                )
            )

        next_player_hand = PlayerHand(
            seat_id=player_hand.seat_id,
            concealed_tiles=concealed,
            drawn_tile=None,
            melds=player_hand.melds,
            bonus_tiles=player_hand.bonus_tiles,
            initial_tile_ids=player_hand.initial_tile_ids,
        )
        sequence = len(hand.discards) + 1
        window_id = _discard_window_id(hand.hand_id, sequence)
        discard = DiscardState(
            sequence=sequence,
            tile=discarded,
            discarded_by_seat_id=action.seat_id,
        )
        next_hand = HandState(
            hand_id=hand.hand_id,
            tile_id_salt=hand.tile_id_salt,
            phase=DiscardClaimsPhase(
                window_id=window_id,
                discard_sequence=sequence,
                eligible_seat_ids=(),
            ),
            wall=hand.wall,
            player_hands=_replace_player_hand(hand, next_player_hand),
            discards=(*hand.discards, discard),
            pending_claims=(),
            payments=hand.payments,
        )
        next_state = _room_with_hand(state, next_hand, pending_deadline=None)
        validate_milestone_three_room(next_state)
        return TransitionResult(
            state=next_state,
            domain_events=(
                TileDiscarded(
                    seat_id=action.seat_id,
                    tile=discarded,
                    discard_sequence=sequence,
                ),
            ),
            effects=(
                ClaimWindowRequested(
                    window_id=window_id,
                    discard_sequence=sequence,
                    eligible_seat_ids=(),
                    duration_ms=3000,
                ),
            ),
        )

    def resolve_discard_window(
        self, state: RoomState, window_id: WindowId
    ) -> TransitionResult:
        _require_milestone_three(state)
        if state.match is None or state.match.current_hand is None:
            raise IllegalGameActionError()
        hand = state.match.current_hand
        if (
            not isinstance(hand.phase, DiscardClaimsPhase)
            or hand.phase.window_id != window_id
            or not hand.discards
            or hand.discards[-1].sequence != hand.phase.discard_sequence
        ):
            raise IllegalGameActionError()
        discarder = hand.discards[-1].discarded_by_seat_id
        seats = tuple(sorted(state.seats, key=lambda seat: seat.slot))
        discarder_index = next(
            index for index, seat in enumerate(seats) if seat.seat_id == discarder
        )
        next_seat_id = seats[(discarder_index + 1) % len(seats)].seat_id
        awaiting_draw = HandState(
            hand_id=hand.hand_id,
            tile_id_salt=hand.tile_id_salt,
            phase=AwaitingDrawPhase(seat_id=next_seat_id),
            wall=hand.wall,
            player_hands=hand.player_hands,
            discards=hand.discards,
            pending_claims=(),
            payments=hand.payments,
        )
        cleared = _room_with_hand(state, awaiting_draw, pending_deadline=None)
        drawn = self._automatic_draw(cleared, next_seat_id)
        result = TransitionResult(
            state=drawn.state,
            domain_events=(
                DiscardWindowResolved(
                    window_id=window_id,
                    discard_sequence=hand.phase.discard_sequence,
                ),
                *drawn.domain_events,
            ),
            effects=drawn.effects,
        )
        validate_milestone_three_room(result.state)
        return result

    def _automatic_draw(
        self, state: RoomState, seat_id: SeatId
    ) -> TransitionResult:
        if state.match is None or state.match.current_hand is None:
            raise InvalidGameStateError("active match has no hand")
        hand = state.match.current_hand
        if not isinstance(hand.phase, AwaitingDrawPhase) or hand.phase.seat_id != seat_id:
            raise InvalidGameStateError("automatic draw does not match the phase")
        live = list(hand.wall.live_tiles)
        reserve = list(hand.wall.reserve_tiles)
        player_hand = _player_hand(hand, seat_id)
        if player_hand.drawn_tile is not None:
            raise InvalidGameStateError("draw buffer must be empty before a draw")
        if not live:
            completed = _complete_tie(state, hand)
            result = completed.match.current_hand.result  # type: ignore[union-attr]
            if result is None:  # pragma: no cover - construction invariant
                raise InvalidGameStateError("completed hand is missing its result")
            return TransitionResult(
                state=completed,
                domain_events=(HandCompleted(result=result),),
                effects=(MatchCompletionRequested(),),
            )

        events: list[DomainEvent] = []
        bonus = list(player_hand.bonus_tiles)
        selected = live.pop(0)
        events.append(TileDrawn(seat_id=seat_id, tile=selected, replacement=False))
        drawn_tile: PhysicalTile | None
        if is_bonus_tile(selected):
            bonus.append(selected)
            events.append(BonusExposed(seat_id=seat_id, tile=selected, initial=False))
            drawn_tile = _replacement_chain(
                seat_id,
                live,
                reserve,
                bonus,
                events,
            )
        else:
            drawn_tile = selected

        next_player_hand = PlayerHand(
            seat_id=player_hand.seat_id,
            concealed_tiles=player_hand.concealed_tiles,
            drawn_tile=drawn_tile,
            melds=player_hand.melds,
            bonus_tiles=tuple(bonus),
            initial_tile_ids=player_hand.initial_tile_ids,
        )
        next_phase = (
            CompletePhase()
            if not live or drawn_tile is None
            else AwaitingDiscardPhase(seat_id=seat_id)
        )
        result_value = (
            HandResult(
                outcome=HandOutcome.TIE,
                reason="LIVE_WALL_EXHAUSTED",
            )
            if isinstance(next_phase, CompletePhase)
            else None
        )
        next_hand = HandState(
            hand_id=hand.hand_id,
            tile_id_salt=hand.tile_id_salt,
            phase=next_phase,
            wall=WallState(live_tiles=tuple(live), reserve_tiles=tuple(reserve)),
            player_hands=_replace_player_hand(hand, next_player_hand),
            discards=hand.discards,
            pending_claims=(),
            payments=hand.payments,
            result=result_value,
        )
        next_state = _room_with_hand(state, next_hand, pending_deadline=None)
        if isinstance(next_phase, CompletePhase):
            if result_value is None:  # pragma: no cover - construction invariant
                raise InvalidGameStateError("completed hand is missing its result")
            events.append(HandCompleted(result=result_value))
            effects: tuple[DomainEffect, ...] = (MatchCompletionRequested(),)
        elif _is_automated(state, seat_id):
            effects = (AutomatedDecisionRequested(seat_id=seat_id),)
        else:
            effects = ()
        return TransitionResult(
            state=next_state,
            domain_events=tuple(events),
            effects=effects,
        )


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
        events.append(
            TileDrawn(seat_id=seat_id, tile=replacement, replacement=True)
        )
        if not is_bonus_tile(replacement):
            return replacement
        bonus.append(replacement)
        events.append(
            BonusExposed(seat_id=seat_id, tile=replacement, initial=False)
        )
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


def finalize_completed_preview(
    state: RoomState, *, completed_at_ms: int
) -> RoomState:
    """Finalize a clock-free completed hand using room-sampled time."""

    _require_milestone_three(state)
    if (
        not isinstance(completed_at_ms, int)
        or isinstance(completed_at_ms, bool)
        or completed_at_ms < 0
    ):
        raise ValueError("completed_at_ms must be a non-negative integer")
    if state.status is RoomStatus.FINISHED:
        validate_milestone_three_room(state, require_deadline=True)
        return state
    validate_milestone_three_room(state)
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
        ()
        if hand.result.winner_seat_id is None
        else (hand.result.winner_seat_id,)
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
    validate_milestone_three_room(finalized, require_deadline=True)
    return finalized


def validate_milestone_three_room(
    state: RoomState, *, require_deadline: bool = False
) -> None:
    """Validate exact M3 ruleset invariants beyond generic future-proof models."""

    _require_milestone_three(state)
    if state.state_schema_version != MILESTONE_3_STATE_SCHEMA_VERSION:
        raise InvalidGameStateError("draw/discard preview requires schema version 3")
    match = state.match
    if match is None or match.status is MatchStatus.PENDING_SETUP:
        if state.pending_deadline is not None:
            raise InvalidGameStateError("pending setup cannot carry a deadline")
        return
    hand = match.current_hand
    if hand is None:
        raise InvalidGameStateError("preview match must retain its current hand")
    if match.prevailing_wind is not Wind.EAST:
        raise InvalidGameStateError("preview prevailing wind must be East")
    if any(balance.points != 0 for balance in match.balances):
        raise InvalidGameStateError("preview balances must remain zero")
    if len(hand.wall.reserve_tiles) != 15:
        raise InvalidGameStateError("replacement reserve must contain 15 tiles")
    if hand.pending_claims or hand.payments:
        raise InvalidGameStateError("preview cannot contain claims or payments")
    if any(player_hand.melds for player_hand in hand.player_hands):
        raise InvalidGameStateError("preview cannot contain melds")
    if any(discard.claim_kind is not None for discard in hand.discards):
        raise InvalidGameStateError("preview discards cannot be claimed")
    if any(is_bonus_tile(discard.tile) for discard in hand.discards):
        raise InvalidGameStateError("preview bonus tiles cannot be discarded")
    if hand.tile_id_salt is None or re.fullmatch(
        r"[0-9a-f]{64}", hand.tile_id_salt
    ) is None:
        raise InvalidGameStateError("preview hand requires opaque tile identity salt")
    ordered_seat_ids = tuple(
        seat.seat_id for seat in sorted(state.seats, key=lambda seat: seat.slot)
    )
    if tuple(player_hand.seat_id for player_hand in hand.player_hands) != (
        ordered_seat_ids
    ):
        raise InvalidGameStateError("preview hands must follow stable seat order")
    if tuple(balance.seat_id for balance in match.balances) != ordered_seat_ids:
        raise InvalidGameStateError("preview balances must follow stable seat order")
    dealer_index = ordered_seat_ids.index(match.dealer_seat_id)
    for discard_index, discard in enumerate(hand.discards):
        expected_discarder = ordered_seat_ids[
            (dealer_index + discard_index) % len(ordered_seat_ids)
        ]
        if discard.discarded_by_seat_id != expected_discarder:
            raise InvalidGameStateError(
                "preview discards must follow cyclic seat order"
            )
    if hand.result is not None:
        _validate_preview_result(hand.result)
    for historical_result in match.hand_history:
        _validate_preview_result(historical_result)

    all_tiles: list[PhysicalTile] = [
        *hand.wall.live_tiles,
        *hand.wall.reserve_tiles,
    ]
    for player_hand in hand.player_hands:
        if len(player_hand.initial_tile_ids) != 13:
            raise InvalidGameStateError("each seat requires 13 raw initial tile IDs")
        if any(is_bonus_tile(tile) for tile in player_hand.concealed_tiles):
            raise InvalidGameStateError("concealed tiles cannot contain bonuses")
        if player_hand.drawn_tile is not None and is_bonus_tile(
            player_hand.drawn_tile
        ):
            raise InvalidGameStateError("draw buffer cannot contain a bonus")
        if any(not is_bonus_tile(tile) for tile in player_hand.bonus_tiles):
            raise InvalidGameStateError("bonus area can contain only bonus tiles")
        if player_hand.concealed_tiles != sort_playable_tiles(
            player_hand.concealed_tiles
        ):
            raise InvalidGameStateError("concealed tiles must use server sort order")
        all_tiles.extend(player_hand.concealed_tiles)
        all_tiles.extend(player_hand.bonus_tiles)
        if player_hand.drawn_tile is not None:
            all_tiles.append(player_hand.drawn_tile)
    all_tiles.extend(discard.tile for discard in hand.discards)

    tile_ids = [tile.tile_id for tile in all_tiles]
    if len(all_tiles) != 148 or len(tile_ids) != len(set(tile_ids)):
        raise InvalidGameStateError("preview must conserve 148 physical tiles")
    expected = {
        tile.tile_id: tile
        for tile in _opaque_physical_deck(hand.hand_id, hand.tile_id_salt)
    }
    actual = {tile.tile_id: tile for tile in all_tiles}
    if actual != expected:
        raise InvalidGameStateError("preview tiles do not match the canonical deck")
    if Counter((tile.face.family, tile.face.value) for tile in all_tiles) != (
        canonical_face_counts()
    ):
        raise InvalidGameStateError("preview logical tile counts are invalid")

    initial_ids = [
        tile_id
        for player_hand in hand.player_hands
        for tile_id in player_hand.initial_tile_ids
    ]
    if len(initial_ids) != 52 or len(initial_ids) != len(set(initial_ids)):
        raise InvalidGameStateError("raw initial provenance must contain 52 tiles")
    if not set(initial_ids).issubset(actual):
        raise InvalidGameStateError("initial provenance references an unknown tile")
    wall_ids = {
        tile.tile_id
        for tile in (*hand.wall.live_tiles, *hand.wall.reserve_tiles)
    }
    held_by_seat = {
        tile.tile_id: player_hand.seat_id
        for player_hand in hand.player_hands
        for tile in (
            *player_hand.concealed_tiles,
            *player_hand.bonus_tiles,
        )
    }
    discarded_by_seat = {
        discard.tile.tile_id: discard.discarded_by_seat_id
        for discard in hand.discards
    }
    for player_hand in hand.player_hands:
        for initial_id in player_hand.initial_tile_ids:
            if (
                initial_id in wall_ids
                or (
                    held_by_seat.get(initial_id) != player_hand.seat_id
                    and discarded_by_seat.get(initial_id) != player_hand.seat_id
                )
            ):
                raise InvalidGameStateError(
                    "raw initial provenance is not attributable to its seat"
                )

    for player_hand in hand.player_hands:
        if len(player_hand.concealed_tiles) != 13:
            raise InvalidGameStateError("every preview seat needs 13 concealed tiles")
    drawn_seats = tuple(
        player_hand.seat_id
        for player_hand in hand.player_hands
        if player_hand.drawn_tile is not None
    )
    expected_active_seat = ordered_seat_ids[
        (dealer_index + len(hand.discards)) % len(ordered_seat_ids)
    ]
    if isinstance(hand.phase, AwaitingDiscardPhase):
        if drawn_seats != (hand.phase.seat_id,):
            raise InvalidGameStateError("discard phase requires one matching draw")
        if hand.phase.seat_id != expected_active_seat:
            raise InvalidGameStateError("discard phase is out of cyclic turn order")
    elif isinstance(hand.phase, (AwaitingDrawPhase, DiscardClaimsPhase)):
        if drawn_seats:
            raise InvalidGameStateError("draw/window phase cannot retain a draw")
        if (
            isinstance(hand.phase, AwaitingDrawPhase)
            and hand.phase.seat_id != expected_active_seat
        ):
            raise InvalidGameStateError("draw phase is out of cyclic turn order")
    elif isinstance(hand.phase, CompletePhase):
        if len(drawn_seats) > 1:
            raise InvalidGameStateError("complete preview has too many drawn tiles")
        if drawn_seats and drawn_seats != (expected_active_seat,):
            raise InvalidGameStateError("final draw is out of cyclic turn order")
    else:
        raise InvalidGameStateError("preview contains an unsupported hand phase")

    if isinstance(hand.phase, CompletePhase):
        if hand.wall.live_tiles:
            raise InvalidGameStateError("wall tie requires an exhausted live wall")
        if match.status is MatchStatus.ACTIVE and require_deadline:
            raise InvalidGameStateError(
                "completed preview must be finalized before persistence"
            )
    elif not hand.wall.live_tiles:
        raise InvalidGameStateError("an unfinished preview requires live wall tiles")

    if isinstance(hand.phase, DiscardClaimsPhase):
        if hand.phase.eligible_seat_ids:
            raise InvalidGameStateError("preview discard window has no claimants")
        if hand.phase.window_id != _discard_window_id(
            hand.hand_id, hand.phase.discard_sequence
        ):
            raise InvalidGameStateError("preview discard window ID is not canonical")
        if require_deadline and state.pending_deadline is None:
            raise InvalidGameStateError("discard window requires a persisted deadline")
    elif state.pending_deadline is not None:
        raise InvalidGameStateError("deadline exists outside a discard window")

    if match.status is MatchStatus.FINISHED:
        if state.status is not RoomStatus.FINISHED:
            raise InvalidGameStateError("finished match requires a finished room")
        if not isinstance(hand.phase, CompletePhase) or hand.result is None:
            raise InvalidGameStateError("finished preview must retain its final hand")
        if match.hand_history != (hand.result,):
            raise InvalidGameStateError(
                "preview history must contain exactly its final hand result"
            )
        if match.result is None:
            raise InvalidGameStateError("finished preview requires a match result")
        if (
            match.result.winning_seat_ids
            or match.result.reason != "LIVE_WALL_EXHAUSTED"
            or any(balance.points != 0 for balance in match.result.final_balances)
            or match.result.final_balances != match.balances
        ):
            raise InvalidGameStateError("finished preview match result is invalid")
    elif match.hand_history:
        raise InvalidGameStateError("active preview cannot contain hand history")


def _validate_preview_result(result: HandResult) -> None:
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
        raise InvalidGameStateError("preview hand result must be an unscored wall tie")


def _require_milestone_three(state: RoomState) -> None:
    if state.ruleset_version != MILESTONE_3_RULESET_VERSION:
        raise InvalidGameStateError("room is not pinned to the draw/discard preview")


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


_MILESTONE_ONE_ENGINE = MilestoneOneEngine()


def transition(state: RoomState, action: DomainAction) -> TransitionResult:
    if state.ruleset_version == MILESTONE_3_RULESET_VERSION:
        return MilestoneThreeEngine().transition(state, action)
    return _MILESTONE_ONE_ENGINE.transition(state, action)


def legal_actions(state: RoomState, seat_id: SeatId) -> tuple[DomainAction, ...]:
    if state.ruleset_version == MILESTONE_3_RULESET_VERSION:
        return MilestoneThreeEngine().legal_actions(state, seat_id)
    return _MILESTONE_ONE_ENGINE.legal_actions(state, seat_id)


__all__ = [
    "GameEngine",
    "GameplayUnavailableError",
    "IllegalGameActionError",
    "InvalidGameStateError",
    "MAX_AUTOMATED_CONTINUATIONS",
    "MILESTONE_1_CAPABILITIES",
    "MilestoneOneEngine",
    "MilestoneThreeEngine",
    "ObservationBuilder",
    "ProjectionBuilder",
    "TransitionResult",
    "finalize_completed_preview",
    "legal_actions",
    "transition",
    "validate_milestone_three_room",
]
