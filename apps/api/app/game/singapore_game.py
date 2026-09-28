"""Clock-free Singapore gameplay; room orchestration owns deadlines and bots."""

from __future__ import annotations

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
    _GameSetup,
    TransitionResult,
    IllegalGameActionError,
    InvalidGameStateError,
    _complete_tie,
    _discard_window_id,
    _is_automated,
    _opaque_physical_deck,
    _player_hand,
    _replace_player_hand,
    _replacement_chain,
    _room_with_hand,
    _validate_tie_result,
)
from .events import (
    BonusExposed,
    ClaimSubmitted,
    DiscardWindowResolved,
    HandCompleted,
    MeldDeclared,
    TileDiscarded,
    TileDrawn,
)
from .model import (
    AwaitingDiscardPhase,
    AwaitingDrawPhase,
    ClaimKind,
    CompletePhase,
    DiscardClaimsPhase,
    DiscardState,
    FinalTileDecisionPhase,
    HandState,
    KongReplacementPhase,
    MatchStatus,
    MeldKind,
    MeldState,
    PendingClaim,
    RoomState,
    RoomStatus,
    SeatId,
    WallState,
    Wind,
    WindowId,
)
from .tiles import is_bonus_tile, sort_playable_tiles

Model = TypeVar("Model", bound=GameModel)


def _updated(model: Model, **updates: Any) -> Model:
    return type(model).model_validate({**model.model_dump(), **updates})


def _seats(state: RoomState) -> tuple[SeatId, ...]:
    return tuple(s.seat_id for s in sorted(state.seats, key=lambda s: s.slot))


class SingaporeGameEngine(_GameSetup):
    capabilities = ROOM_CAPABILITIES

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
