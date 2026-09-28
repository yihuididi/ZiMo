"""Clock-free Singapore match setup and gameplay."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, TypeVar

from .actions import Discard, DomainAction, FinishHand, Kong, Pong
from .base import GameModel
from .capabilities import ROOM_CAPABILITIES
from .claims import claim_actions, concealed_kongs, winning_claim
from .effects import (
    AutomatedDecisionRequested,
    ClaimWindowRequested,
    MatchCompletionRequested,
)
from .engine import (
    MAX_AUTOMATED_CONTINUATIONS,
    IllegalGameActionError,
    InvalidGameStateError,
    TransitionResult,
)
from .events import (
    BonusExposed,
    ClaimSubmitted,
    DiscardWindowResolved,
    DomainEvent,
    HandCompleted,
    HandSetupCompleted,
    MeldDeclared,
    TileDiscarded,
    TileDrawn,
)
from .model import (
    AutomatedSeatController,
    AwaitingDiscardPhase,
    AwaitingDrawPhase,
    ClaimKind,
    CompletePhase,
    DiscardClaimsPhase,
    DiscardState,
    FinalTileDecisionPhase,
    HandId,
    HandOutcome,
    HandResult,
    HandState,
    KongReplacementPhase,
    MatchResult,
    MatchState,
    MatchStatus,
    MeldKind,
    MeldState,
    PendingClaim,
    PhysicalTile,
    PlayerHand,
    RoomState,
    RoomStatus,
    SeatId,
    WallState,
    Wind,
    WindowId,
)
from .runtime import RandomSource, SystemRandomSource
from .tiles import canonical_physical_deck, is_bonus_tile, sort_playable_tiles


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

    if (
        not isinstance(completed_at_ms, int)
        or isinstance(completed_at_ms, bool)
        or completed_at_ms < 0
    ):
        raise ValueError("completed_at_ms must be a non-negative integer")
    if state.status is RoomStatus.FINISHED:
        validate_room(state, require_deadline=True)
        return state
    validate_room(state)
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
    validate_room(finalized, require_deadline=True)
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


Model = TypeVar("Model", bound=GameModel)


def _updated(model: Model, **updates: Any) -> Model:
    return type(model).model_validate({**model.model_dump(), **updates})


def _seats(state: RoomState) -> tuple[SeatId, ...]:
    return tuple(s.seat_id for s in sorted(state.seats, key=lambda s: s.slot))


class SingaporeGameEngine:
    capabilities = ROOM_CAPABILITIES

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

    def _require(self, state: RoomState) -> None:
        if state.ruleset_id != "singapore":
            raise InvalidGameStateError("room does not use Singapore rules")

    def _validate(self, state: RoomState) -> None:
        validate_room(state)

    def legal_actions(
        self, state: RoomState, seat_id: SeatId
    ) -> tuple[DomainAction, ...]:
        self._require(state)
        if (
            state.status is not RoomStatus.IN_MATCH
            or state.match is None
            or state.match.status is not MatchStatus.ACTIVE
            or state.match.current_hand is None
        ):
            return ()
        hand = state.match.current_hand
        phase = hand.phase
        if isinstance(phase, DiscardClaimsPhase):
            if seat_id not in phase.eligible_seat_ids or any(
                c.seat_id == seat_id for c in hand.pending_claims
            ):
                return ()
            return claim_actions(hand, seat_id, _seats(state))
        if (
            not isinstance(phase, (AwaitingDiscardPhase, FinalTileDecisionPhase))
            or phase.seat_id != seat_id
        ):
            return ()
        player = _player_hand(hand, seat_id)
        if isinstance(phase, FinalTileDecisionPhase):
            return (*concealed_kongs(player), FinishHand(seat_id=seat_id))
        kongs = concealed_kongs(player) if player.drawn_tile else ()
        return (
            *kongs,
            *(
                Discard(seat_id=seat_id, tile_id=t.tile_id)
                for t in (
                    *player.concealed_tiles,
                    *((player.drawn_tile,) if player.drawn_tile else ()),
                )
            ),
        )

    def transition(self, state: RoomState, action: DomainAction) -> TransitionResult:
        if action not in self.legal_actions(state, action.seat_id):
            raise IllegalGameActionError()
        hand = state.match.current_hand
        player = _player_hand(hand, action.seat_id)
        if isinstance(hand.phase, DiscardClaimsPhase):
            kind = {
                "chow": ClaimKind.CHOW,
                "pong": ClaimKind.PONG,
                "kong": ClaimKind.KONG,
                "pass": ClaimKind.PASS,
            }[action.type]
            claim = PendingClaim(
                window_id=hand.phase.window_id,
                seat_id=action.seat_id,
                kind=kind,
                tile_ids=getattr(action, "tile_ids", ()),
            )
            updated = _updated(hand, pending_claims=(*hand.pending_claims, claim))
            result = TransitionResult(
                state=_room_with_hand(
                    state, updated, pending_deadline=state.pending_deadline
                ),
                domain_events=(
                    ClaimSubmitted(
                        window_id=claim.window_id, seat_id=claim.seat_id, kind=kind
                    ),
                ),
            )
        elif isinstance(action, FinishHand):
            result = self._finish(state, hand)
        elif isinstance(action, Kong):
            tiles = (
                *player.concealed_tiles,
                *((player.drawn_tile,) if player.drawn_tile else ()),
            )
            meld = MeldState(
                kind=MeldKind.KONG,
                kong_kind="KONG_4",
                tiles=tuple(t for t in tiles if t.tile_id in action.tile_ids),
            )
            player = _updated(
                player,
                concealed_tiles=sort_playable_tiles(
                    t for t in tiles if t.tile_id not in action.tile_ids
                ),
                drawn_tile=None,
                melds=(*player.melds, meld),
                passed_pong_faces=(),
            )
            updated = _updated(
                hand,
                player_hands=_replace_player_hand(hand, player),
                phase=KongReplacementPhase(seat_id=action.seat_id),
            )
            changed = _room_with_hand(state, updated, pending_deadline=None)
            continuation = self._draw(changed, action.seat_id, replacement=True)
            result = _updated(
                continuation,
                domain_events=(
                    MeldDeclared(seat_id=action.seat_id, meld=meld),
                    *continuation.domain_events,
                ),
            )
        elif isinstance(action, Discard):
            tiles = (
                *player.concealed_tiles,
                *((player.drawn_tile,) if player.drawn_tile else ()),
            )
            tile = next(t for t in tiles if t.tile_id == action.tile_id)
            player = _updated(
                player,
                concealed_tiles=sort_playable_tiles(
                    t for t in tiles if t.tile_id != action.tile_id
                ),
                drawn_tile=None,
                last_discard_face=tile.face,
            )
            sequence = len(hand.discards) + 1
            window = _discard_window_id(hand.hand_id, sequence)
            phase = DiscardClaimsPhase(
                window_id=window,
                discard_sequence=sequence,
                opening_revision=state.revision + 1,
            )
            updated = _updated(
                hand,
                phase=phase,
                player_hands=_replace_player_hand(hand, player),
                discards=(
                    *hand.discards,
                    DiscardState(
                        sequence=sequence,
                        tile=tile,
                        discarded_by_seat_id=action.seat_id,
                    ),
                ),
                pending_claims=(),
            )
            eligible = tuple(
                seat
                for seat in _seats(state)
                if claim_actions(updated, seat, _seats(state))
            )
            updated = _updated(
                updated, phase=_updated(phase, eligible_seat_ids=eligible)
            )
            result = TransitionResult(
                state=_room_with_hand(state, updated, pending_deadline=None),
                domain_events=(
                    TileDiscarded(
                        seat_id=action.seat_id, tile=tile, discard_sequence=sequence
                    ),
                ),
                effects=(
                    ClaimWindowRequested(
                        window_id=window,
                        discard_sequence=sequence,
                        eligible_seat_ids=eligible,
                        duration_ms=3000,
                    ),
                ),
            )
        else:
            raise IllegalGameActionError()
        self._validate(result.state)
        return result

    def resolve_discard_window(
        self, state: RoomState, window_id: WindowId
    ) -> TransitionResult:
        self._require(state)
        hand = state.match.current_hand if state.match else None
        if (
            hand is None
            or not isinstance(hand.phase, DiscardClaimsPhase)
            or hand.phase.window_id != window_id
        ):
            raise IllegalGameActionError()
        discard = hand.discards[-1]
        seats = _seats(state)
        winner = winning_claim(hand.pending_claims, seats, discard.discarded_by_seat_id)
        claims = {c.seat_id: c for c in hand.pending_claims}
        players = []
        for player in hand.player_hands:
            offered = claim_actions(hand, player.seat_id, seats)
            chosen = claims.get(player.seat_id)
            if any(isinstance(a, Pong) for a in offered) and (
                chosen is None or chosen.kind not in {ClaimKind.PONG, ClaimKind.KONG}
            ):
                player = _updated(
                    player,
                    passed_pong_faces=(*player.passed_pong_faces, discard.tile.face),
                )
            players.append(player)
        resolution = DiscardWindowResolved(
            window_id=window_id,
            discard_sequence=discard.sequence,
            winning_seat_id=winner.seat_id if winner else None,
            claim_kind=winner.kind if winner else None,
        )
        if winner is None:
            seat = seats[(seats.index(discard.discarded_by_seat_id) + 1) % 4]
            updated = _updated(
                hand,
                phase=AwaitingDrawPhase(seat_id=seat),
                pending_claims=(),
                player_hands=tuple(players),
            )
            result = self._automatic_draw(
                _room_with_hand(state, updated, pending_deadline=None), seat
            )
            result = _updated(result, domain_events=(resolution, *result.domain_events))
        else:
            player = next(p for p in players if p.seat_id == winner.seat_id)
            meld = MeldState(
                kind={
                    ClaimKind.CHOW: MeldKind.CHOW,
                    ClaimKind.PONG: MeldKind.PONG,
                    ClaimKind.KONG: MeldKind.KONG,
                }[winner.kind],
                kong_kind="KONG_3" if winner.kind is ClaimKind.KONG else None,
                tiles=tuple(
                    t for t in player.concealed_tiles if t.tile_id in winner.tile_ids
                )
                + (discard.tile,),
                claimed_from_seat_id=discard.discarded_by_seat_id,
                discard_sequence=discard.sequence,
            )
            player = _updated(
                player,
                concealed_tiles=tuple(
                    t
                    for t in player.concealed_tiles
                    if t.tile_id not in winner.tile_ids
                ),
                melds=(*player.melds, meld),
                passed_pong_faces=(),
            )
            phase = (
                KongReplacementPhase(seat_id=winner.seat_id)
                if winner.kind is ClaimKind.KONG
                else AwaitingDiscardPhase(seat_id=winner.seat_id)
            )
            updated = _updated(
                hand,
                phase=phase,
                pending_claims=(),
                player_hands=tuple(
                    player if p.seat_id == player.seat_id else p for p in players
                ),
                discards=(
                    *hand.discards[:-1],
                    _updated(
                        discard,
                        claimed_by_seat_id=winner.seat_id,
                        claim_kind=winner.kind,
                    ),
                ),
            )
            changed = _room_with_hand(state, updated, pending_deadline=None)
            result = (
                self._draw(changed, winner.seat_id, replacement=True)
                if winner.kind is ClaimKind.KONG
                else self._await_turn(changed, winner.seat_id)
            )
            result = _updated(
                result,
                domain_events=(
                    resolution,
                    MeldDeclared(seat_id=winner.seat_id, meld=meld),
                    *result.domain_events,
                ),
            )
        self._validate(result.state)
        return result

    def _automatic_draw(self, state: RoomState, seat_id: SeatId) -> TransitionResult:
        return self._draw(state, seat_id, replacement=False)

    def _draw(
        self, state: RoomState, seat_id: SeatId, *, replacement: bool
    ) -> TransitionResult:
        hand = state.match.current_hand
        if not hand.wall.live_tiles:
            return self._finish(state, hand)
        player = _player_hand(hand, seat_id)
        live, reserve, bonus, events = (
            list(hand.wall.live_tiles),
            list(hand.wall.reserve_tiles),
            list(player.bonus_tiles),
            [],
        )
        if replacement:
            tile = _replacement_chain(seat_id, live, reserve, bonus, events)
        else:
            tile = live.pop(0)
            events.append(TileDrawn(seat_id=seat_id, tile=tile, replacement=False))
            if is_bonus_tile(tile):
                bonus.append(tile)
                events.append(BonusExposed(seat_id=seat_id, tile=tile, initial=False))
                tile = _replacement_chain(seat_id, live, reserve, bonus, events)
        player = _updated(
            player, drawn_tile=tile, bonus_tiles=tuple(bonus), passed_pong_faces=()
        )
        final = not live or tile is None
        phase = (
            FinalTileDecisionPhase(seat_id=seat_id)
            if final
            else AwaitingDiscardPhase(seat_id=seat_id)
        )
        updated = _updated(
            hand,
            phase=phase,
            wall=WallState(live_tiles=tuple(live), reserve_tiles=tuple(reserve)),
            player_hands=_replace_player_hand(hand, player),
        )
        changed = _room_with_hand(state, updated, pending_deadline=None)
        result = (
            self._finish(changed, updated)
            if final and (tile is None or not concealed_kongs(player))
            else self._await_turn(changed, seat_id)
        )
        return _updated(result, domain_events=(*events, *result.domain_events))

    @staticmethod
    def _await_turn(state: RoomState, seat_id: SeatId) -> TransitionResult:
        return TransitionResult(
            state=state,
            effects=(
                (AutomatedDecisionRequested(seat_id=seat_id),)
                if _is_automated(state, seat_id)
                else ()
            ),
        )

    @staticmethod
    def _finish(state: RoomState, hand: HandState) -> TransitionResult:
        completed = _complete_tie(state, hand)
        return TransitionResult(
            state=completed,
            domain_events=(HandCompleted(result=completed.match.current_hand.result),),
            effects=(MatchCompletionRequested(),),
        )


def validate_room(
    state: RoomState, *, require_deadline: bool = False
) -> None:
    if state.ruleset_id != "singapore":
        raise InvalidGameStateError("room does not use Singapore rules")
    hand = state.match.current_hand if state.match else None
    if hand is None:
        if (
            state.match is not None
            and state.match.status is not MatchStatus.PENDING_SETUP
        ):
            raise InvalidGameStateError("active match requires a hand")
        if state.pending_deadline is not None:
            raise InvalidGameStateError("deadline without hand")
        return
    if not isinstance(
        hand.phase,
        (
            AwaitingDrawPhase,
            AwaitingDiscardPhase,
            DiscardClaimsPhase,
            KongReplacementPhase,
            FinalTileDecisionPhase,
            CompletePhase,
        ),
    ):
        raise InvalidGameStateError("unsupported game phase")
    if require_deadline and isinstance(
        hand.phase, (AwaitingDrawPhase, KongReplacementPhase)
    ):
        raise InvalidGameStateError(
            "automatic continuation must complete before persistence"
        )
    if tuple(p.seat_id for p in hand.player_hands) != _seats(state):
        raise InvalidGameStateError("hands must follow stable seat order")
    # Revalidate all structural ownership and immutable discard provenance rules.
    HandState.model_validate_json(hand.canonical_json(), strict=True)
    if len(hand.wall.reserve_tiles) != 15 or hand.tile_id_salt is None:
        raise InvalidGameStateError("invalid wall or tile identity")
    tiles = [
        *hand.wall.live_tiles,
        *hand.wall.reserve_tiles,
        *(d.tile for d in hand.discards if d.claimed_by_seat_id is None),
    ]
    for player in hand.player_hands:
        tiles.extend(
            (
                *player.concealed_tiles,
                *player.bonus_tiles,
                *((player.drawn_tile,) if player.drawn_tile else ()),
                *(t for m in player.melds for t in m.tiles),
            )
        )
        if player.concealed_tiles != sort_playable_tiles(player.concealed_tiles) or any(
            is_bonus_tile(t) for t in player.concealed_tiles
        ):
            raise InvalidGameStateError("invalid concealed tiles")
        if any(not is_bonus_tile(t) for t in player.bonus_tiles) or (
            player.drawn_tile and is_bonus_tile(player.drawn_tile)
        ):
            raise InvalidGameStateError("invalid bonus placement")
        if len(player.initial_tile_ids) != 13 or len(
            set(player.passed_pong_faces)
        ) != len(player.passed_pong_faces):
            raise InvalidGameStateError("invalid initial provenance or passed faces")
        own_discards = [
            d for d in hand.discards if d.discarded_by_seat_id == player.seat_id
        ]
        if player.last_discard_face != (
            own_discards[-1].tile.face if own_discards else None
        ):
            raise InvalidGameStateError(
                "last discard restriction disagrees with ledger"
            )
        if player.drawn_tile and (
            not isinstance(
                hand.phase,
                (AwaitingDiscardPhase, FinalTileDecisionPhase, CompletePhase),
            )
            or (hasattr(hand.phase, "seat_id") and hand.phase.seat_id != player.seat_id)
        ):
            raise InvalidGameStateError("draw buffer belongs only to the active seat")
        for meld in player.melds:
            if meld.kind is not MeldKind.KONG and (
                meld.kong_kind is not None
                or meld.discard_sequence is None
                or meld.concealed
            ):
                raise InvalidGameStateError("invalid claimed meld provenance")
            faces = [t.face for t in meld.tiles]
            if meld.kind is MeldKind.CHOW:
                if (
                    len({f.family for f in faces}) != 1
                    or any(not isinstance(f.value, int) for f in faces)
                    or sorted(f.value for f in faces)
                    != list(
                        range(
                            min(f.value for f in faces), min(f.value for f in faces) + 3
                        )
                    )
                    or any(is_bonus_tile(t) for t in meld.tiles)
                ):
                    raise InvalidGameStateError("invalid Chow")
            elif len(set(faces)) != 1 or any(is_bonus_tile(t) for t in meld.tiles):
                raise InvalidGameStateError("invalid matching meld")
            if meld.kind is MeldKind.KONG and (
                meld.concealed
                or meld.kong_kind != ("KONG_3" if meld.discard_sequence else "KONG_4")
            ):
                raise InvalidGameStateError("invalid Kong provenance")
        count = (
            len(player.concealed_tiles)
            + (player.drawn_tile is not None)
            + 3 * len(player.melds)
        )
        if isinstance(hand.phase, CompletePhase) and count not in {13, 14}:
            raise InvalidGameStateError("invalid completed hand size")
        if not isinstance(hand.phase, CompletePhase):
            expected = (
                14
                if isinstance(
                    hand.phase, (AwaitingDiscardPhase, FinalTileDecisionPhase)
                )
                and hand.phase.seat_id == player.seat_id
                else 13
            )
            if count != expected:
                raise InvalidGameStateError("invalid phase hand size")
    expected = _opaque_physical_deck(hand.hand_id, hand.tile_id_salt)
    if len(tiles) != 148 or {t.tile_id: t for t in tiles} != {
        t.tile_id: t for t in expected
    }:
        raise InvalidGameStateError("physical tile conservation failed")
    initial_ids = [i for p in hand.player_hands for i in p.initial_tile_ids]
    if len(set(initial_ids)) != 52:
        raise InvalidGameStateError("initial provenance must be unique")
    for player in hand.player_hands:
        attributable = {
            t.tile_id
            for t in (
                *player.concealed_tiles,
                *player.bonus_tiles,
                *((player.drawn_tile,) if player.drawn_tile else ()),
                *(t for m in player.melds for t in m.tiles),
            )
        }
        attributable.update(
            d.tile.tile_id
            for d in hand.discards
            if d.discarded_by_seat_id == player.seat_id
        )
        if not set(player.initial_tile_ids).issubset(attributable):
            raise InvalidGameStateError(
                "initial tiles cannot change owner without a discard"
            )
    if any(is_bonus_tile(d.tile) for d in hand.discards):
        raise InvalidGameStateError("bonus tiles cannot be discarded")
    if (
        hand.payments
        or any(b.points for b in state.match.balances)
        or state.match.prevailing_wind is not Wind.EAST
    ):
        raise InvalidGameStateError("unsupported scoring or round")
    if isinstance(hand.phase, DiscardClaimsPhase):
        if (
            hand.phase.window_id
            != _discard_window_id(hand.hand_id, hand.phase.discard_sequence)
            or hand.phase.opening_revision is None
        ):
            raise InvalidGameStateError("invalid claim window")
        if require_deadline and (
            state.pending_deadline is None
            or hand.phase.opening_revision > state.revision
        ):
            raise InvalidGameStateError("missing deadline or invalid opening revision")
        eligible = tuple(
            seat for seat in _seats(state) if claim_actions(hand, seat, _seats(state))
        )
        if eligible != hand.phase.eligible_seat_ids:
            raise InvalidGameStateError("invalid eligible seats")
        for claim in hand.pending_claims:
            legal = claim_actions(hand, claim.seat_id, _seats(state))
            if not any(
                getattr(a, "tile_ids", ()) == claim.tile_ids
                and {
                    "chow": ClaimKind.CHOW,
                    "pong": ClaimKind.PONG,
                    "kong": ClaimKind.KONG,
                    "pass": ClaimKind.PASS,
                }[a.type]
                == claim.kind
                for a in legal
            ):
                raise InvalidGameStateError("invalid persisted claim")
    elif state.pending_deadline is not None:
        raise InvalidGameStateError("deadline outside window")
    if isinstance(hand.phase, (CompletePhase, FinalTileDecisionPhase)):
        if hand.wall.live_tiles:
            raise InvalidGameStateError("endgame requires exhausted live wall")
    elif not hand.wall.live_tiles:
        raise InvalidGameStateError("active play needs live tiles")
    if isinstance(hand.phase, FinalTileDecisionPhase) and not concealed_kongs(
        _player_hand(hand, hand.phase.seat_id)
    ):
        raise InvalidGameStateError("final decision requires a legal Kong")
    if hand.result:
        _validate_tie_result(hand.result)
        if require_deadline and state.match.status is not MatchStatus.FINISHED:
            raise InvalidGameStateError("completed hand must be finalized")
    if state.match.status is MatchStatus.FINISHED:
        if (
            state.status is not RoomStatus.FINISHED
            or not hand.result
            or state.match.hand_history != (hand.result,)
            or state.match.result is None
            or state.match.result.winning_seat_ids
            or state.match.result.final_balances != state.match.balances
        ):
            raise InvalidGameStateError("invalid finished preview")
