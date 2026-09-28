from __future__ import annotations

import json
import unittest
from collections import Counter
from typing import TypeVar

from pydantic import ValidationError

from app.game import (
    MAX_AUTOMATED_CONTINUATIONS,
    ROOM_CAPABILITIES,
    AutomatedDecisionRequested,
    AutomatedSeatController,
    AwaitingDiscardPhase,
    BonusExposed,
    ClaimWindowRequested,
    CompletePhase,
    DeterministicRandomSource,
    Discard,
    DiscardClaimsPhase,
    DiscardWindowResolved,
    ExternalSeatController,
    HandCompleted,
    HandId,
    HandOutcome,
    HandSetupCompleted,
    IllegalGameActionError,
    InvalidGameStateError,
    MatchCompletionRequested,
    MatchId,
    MatchState,
    MatchStatus,
    SingaporeGameEngine,
    OpaqueActionDescriptor,
    OpponentSeatObservation,
    OpponentSeatView,
    PendingDeadline,
    PlayerId,
    PlayerRole,
    PlayerState,
    PolicyId,
    PublicTileView,
    RoomId,
    RoomState,
    RoomStatus,
    SeatBalance,
    SeatId,
    SeatState,
    SelfSeatView,
    TileDiscarded,
    TileDrawn,
    TileFace,
    TileFamily,
    Wind,
    WindowId,
    build_public_room_view,
    build_seat_observation,
    canonical_face_counts,
    canonical_physical_deck,
    canonical_tile_faces,
    choose_automated_action,
    deserialize_room_state,
    finalize_completed_preview,
    is_bonus_tile,
    serialize_room_state,
    sort_playable_tiles,
    validate_room,
)


T = TypeVar("T")


class IdentityRandomSource:
    """Select seat zero and preserve the canonical deck order."""

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return 0

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        return tuple(values)


class AllBonusChainRandomSource:
    """Place every bonus in one automatic draw/replacement chain."""

    last_order: tuple[object, ...] = ()

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return 0

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        bonuses = [value for value in values if is_bonus_tile(value)]  # type: ignore[arg-type]
        regular = [value for value in values if not is_bonus_tile(value)]  # type: ignore[arg-type]
        self.assert_shape(bonuses, regular)

        raw_initial = regular[:52]
        automatic_bonus = bonuses[0]
        replacement_draw_order = [*bonuses[1:], regular[52]]
        used = {*raw_initial, automatic_bonus, *replacement_draw_order}
        remaining = [value for value in values if value not in used]
        live_filler = remaining[:-3]
        reserve_prefix = remaining[-3:]
        order = (
            *raw_initial,
            automatic_bonus,
            *live_filler,
            *reserve_prefix,
            *reversed(replacement_draw_order),
        )
        if len(order) != 148 or set(order) != set(values):
            raise AssertionError("adversarial fixture must remain a deck permutation")
        self.last_order = tuple(order)
        return tuple(order)

    @staticmethod
    def assert_shape(bonuses: list[T], regular: list[T]) -> None:
        if len(bonuses) != 12 or len(regular) != 136:
            raise AssertionError("canonical Singapore deck shape changed")


class InitialBonusRandomSource:
    """Deal one raw bonus, then provide a regular opposite-end replacement."""

    raw_bonus: object | None = None
    replacement: object | None = None

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return 0

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        bonuses = [value for value in values if is_bonus_tile(value)]  # type: ignore[arg-type]
        regular = [value for value in values if not is_bonus_tile(value)]  # type: ignore[arg-type]
        raw = [bonuses[0], *regular[:51]]
        replacement = regular[51]
        used = {*raw, replacement}
        remaining = [value for value in values if value not in used]
        order = (
            *raw,
            *remaining[:-14],
            *remaining[-14:],
            replacement,
        )
        if len(order) != 148 or set(order) != set(values):
            raise AssertionError("initial-bonus fixture must remain a permutation")
        self.raw_bonus = bonuses[0]
        self.replacement = replacement
        return tuple(order)


class FinalLiveBonusRandomSource:
    """Put one bonus at the final live position and the other bonuses in reserve."""

    final_bonus: object | None = None

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return 0

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        bonuses = [value for value in values if is_bonus_tile(value)]  # type: ignore[arg-type]
        regular = [value for value in values if not is_bonus_tile(value)]  # type: ignore[arg-type]
        order = (
            *regular[:52],
            *regular[52:132],
            bonuses[0],
            *regular[132:],
            *bonuses[1:],
        )
        if len(order) != 148 or set(order) != set(values):
            raise AssertionError("final-bonus fixture must remain a permutation")
        self.final_bonus = bonuses[0]
        return tuple(order)


class DealerTwoInitialBonusRandomSource:
    """Exercise dealer-relative initial exposure and a bonus replacement."""

    _randbelow_calls = 0

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        self._randbelow_calls += 1
        return 2 if self._randbelow_calls == 1 else 0

    def shuffled(self, values: tuple[T, ...]) -> tuple[T, ...]:
        bonuses = [value for value in values if is_bonus_tile(value)]  # type: ignore[arg-type]
        regular = [value for value in values if not is_bonus_tile(value)]  # type: ignore[arg-type]
        raw = [*bonuses[:5], *regular[:47]]
        replacement_draw_order = [bonuses[5], *regular[47:52]]
        used = {*raw, *replacement_draw_order}
        remaining = [value for value in values if value not in used]
        order = (
            *raw,
            *remaining[:81],
            *remaining[81:],
            *reversed(replacement_draw_order),
        )
        if len(order) != 148 or set(order) != set(values):
            raise AssertionError("dealer-two fixture must remain a permutation")
        return tuple(order)


def preview_room(*, human_at_zero: bool = False) -> RoomState:
    seat_ids = tuple(SeatId(f"seat-{index}") for index in range(4))
    human_id = PlayerId("player-0")
    players = (
        (
            PlayerState(
                player_id=human_id,
                display_name="Host",
                role=PlayerRole.HOST,
                ready=True,
                joined_at_ms=1,
            ),
        )
        if human_at_zero
        else ()
    )
    seats = tuple(
        SeatState(
            seat_id=seat_id,
            slot=index,
            controller=(
                ExternalSeatController(player_id=human_id)
                if human_at_zero and index == 0
                else AutomatedSeatController(policy_id=PolicyId("randomBot"))
            ),
            occupant_name="Host" if human_at_zero and index == 0 else f"Bot {index}",
        )
        for index, seat_id in enumerate(seat_ids)
    )
    return RoomState(
        room_id=RoomId("room-preview"),
        revision=7,
        status=RoomStatus.IN_MATCH,
        seats=seats,
        players=players,
        match=MatchState(
            match_id=MatchId("match-preview"),
            status=MatchStatus.PENDING_SETUP,
            dealer_seat_id=None,
            current_hand=None,
            balances=tuple(
                SeatBalance(seat_id=seat_id) for seat_id in seat_ids
            ),
        ),
        created_at_ms=100,
        updated_at_ms=200,
    )


def hand_for_seat(room: RoomState, seat_id: SeatId):
    assert room.match is not None and room.match.current_hand is not None
    return next(
        hand
        for hand in room.match.current_hand.player_hands
        if hand.seat_id == seat_id
    )


def canonical_locations(room: RoomState) -> tuple[str, ...]:
    return tuple(str(tile.tile_id) for tile in canonical_tiles(room))


def canonical_tiles(room: RoomState):
    assert room.match is not None and room.match.current_hand is not None
    hand = room.match.current_hand
    tiles = [
        *hand.wall.live_tiles,
        *hand.wall.reserve_tiles,
        *(discard.tile for discard in hand.discards),
    ]
    for player_hand in hand.player_hands:
        tiles.extend(player_hand.concealed_tiles)
        tiles.extend(player_hand.bonus_tiles)
        if player_hand.drawn_tile is not None:
            tiles.append(player_hand.drawn_tile)
    return tuple(tiles)


class CanonicalTileManifestTests(unittest.TestCase):
    def test_exact_46_faces_and_148_physical_tiles(self) -> None:
        faces = canonical_tile_faces()
        deck = canonical_physical_deck(HandId("hand-manifest"))

        self.assertEqual(len(faces), 46)
        self.assertEqual(len(set(faces)), 46)
        self.assertEqual(len(deck), 148)
        self.assertEqual(len({tile.tile_id for tile in deck}), 148)
        self.assertEqual(
            Counter((tile.face.family, tile.face.value) for tile in deck),
            canonical_face_counts(),
        )
        self.assertEqual(sum(is_bonus_tile(tile) for tile in deck), 12)
        self.assertEqual(
            tuple(face.family for face in faces[:27:9]),
            (
                TileFamily.CHARACTERS,
                TileFamily.DOTS,
                TileFamily.BAMBOO,
            ),
        )

    def test_tile_faces_reject_noncanonical_aliases_and_value_types(self) -> None:
        invalid = (
            {"family": "CHARACTERS", "value": 0},
            {"family": "DOTS", "value": True},
            {"family": "WIND", "value": "E"},
            {"family": "DRAGON", "value": "R"},
            {"family": "FLOWER", "value": "1"},
            {"family": "SEASON", "value": 5},
            {"family": "ANIMAL", "value": "FISH"},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                TileFace.model_validate(value)

    def test_server_sort_order_is_characters_dots_bamboo_then_honours(self) -> None:
        deck = canonical_physical_deck(HandId("hand-sort"))
        selected = (
            next(
                tile
                for tile in deck
                if tile.face == TileFace(family=TileFamily.BAMBOO, value=1)
            ),
            next(
                tile
                for tile in deck
                if tile.face == TileFace(family=TileFamily.DRAGON, value="RED")
            ),
            next(
                tile
                for tile in deck
                if tile.face == TileFace(family=TileFamily.DOTS, value=1)
            ),
            next(
                tile
                for tile in deck
                if tile.face == TileFace(family=TileFamily.WIND, value="EAST")
            ),
            next(
                tile
                for tile in deck
                if tile.face == TileFace(family=TileFamily.CHARACTERS, value=9)
            ),
        )
        self.assertEqual(
            tuple(tile.face.family for tile in sort_playable_tiles(selected)),
            (
                TileFamily.CHARACTERS,
                TileFamily.DOTS,
                TileFamily.BAMBOO,
                TileFamily.WIND,
                TileFamily.DRAGON,
            ),
        )


class SetupAndReplacementTests(unittest.TestCase):
    def test_setup_deals_round_robin_tracks_raw_provenance_and_draws_for_dealer(self) -> None:
        source = IdentityRandomSource()
        initial = preview_room()
        result = SingaporeGameEngine(source).setup_match(initial)
        room = result.state
        assert room.match is not None and room.match.current_hand is not None
        hand = room.match.current_hand
        dealer = SeatId("seat-0")

        self.assertEqual(room.revision, initial.revision)
        self.assertEqual(room.updated_at_ms, initial.updated_at_ms)
        self.assertEqual(room.match.status, MatchStatus.ACTIVE)
        self.assertEqual(room.match.dealer_seat_id, dealer)
        self.assertEqual(room.match.prevailing_wind, Wind.EAST)
        self.assertIsInstance(hand.phase, AwaitingDiscardPhase)
        self.assertEqual(hand.phase.seat_id, dealer)
        self.assertEqual(len(hand.wall.live_tiles), 80)
        self.assertEqual(len(hand.wall.reserve_tiles), 15)
        self.assertEqual(len(canonical_locations(room)), 148)
        self.assertEqual(len(set(canonical_locations(room))), 148)

        canonical = canonical_physical_deck(hand.hand_id)
        actual = {tile.tile_id: tile for tile in canonical_tiles(room)}
        for slot in range(4):
            player_hand = hand_for_seat(room, SeatId(f"seat-{slot}"))
            self.assertEqual(
                tuple(actual[tile_id].face for tile_id in player_hand.initial_tile_ids),
                tuple(tile.face for tile in canonical[slot:52:4]),
            )
            self.assertEqual(len(player_hand.concealed_tiles), 13)
            self.assertEqual(
                player_hand.concealed_tiles,
                sort_playable_tiles(player_hand.concealed_tiles),
            )
            self.assertEqual(player_hand.bonus_tiles, ())
            self.assertEqual(player_hand.drawn_tile is not None, slot == 0)

        self.assertIsInstance(result.domain_events[0], HandSetupCompleted)
        self.assertIsInstance(result.domain_events[-1], TileDrawn)
        self.assertEqual(result.domain_events[-1].seat_id, dealer)
        self.assertFalse(result.domain_events[-1].replacement)
        self.assertRegex(hand.tile_id_salt or "", r"^[0-9a-f]{64}$")
        self.assertTrue(
            all(
                str(tile.tile_id).startswith("tile_")
                for tile in canonical_tiles(room)
            )
        )
        self.assertTrue(
            {tile.tile_id for tile in canonical_tiles(room)}.isdisjoint(
                tile.tile_id for tile in canonical
            )
        )
        self.assertEqual(
            result.effects,
            (AutomatedDecisionRequested(seat_id=dealer),),
        )
        validate_room(room)

    def test_raw_initial_provenance_keeps_exposed_bonus_not_replacement(self) -> None:
        source = InitialBonusRandomSource()
        result = SingaporeGameEngine(source).setup_match(preview_room())
        dealer_hand = hand_for_seat(result.state, SeatId("seat-0"))
        initial_bonus_index = next(
            index
            for index, event in enumerate(result.domain_events)
            if isinstance(event, BonusExposed) and event.initial
        )
        replacement_index = next(
            index
            for index, event in enumerate(result.domain_events)
            if isinstance(event, TileDrawn) and event.replacement
        )
        self.assertLess(initial_bonus_index, replacement_index)
        raw_bonus = result.domain_events[initial_bonus_index].tile  # type: ignore[union-attr]
        replacement = result.domain_events[replacement_index].tile  # type: ignore[union-attr]
        self.assertIn(raw_bonus.tile_id, dealer_hand.initial_tile_ids)
        self.assertNotIn(replacement.tile_id, dealer_hand.initial_tile_ids)
        self.assertIn(raw_bonus, dealer_hand.bonus_tiles)
        self.assertIn(replacement, dealer_hand.concealed_tiles)
        validate_room(result.state)

    def test_all_twelve_bonuses_can_form_one_bounded_replacement_chain(self) -> None:
        source = AllBonusChainRandomSource()
        result = SingaporeGameEngine(source).setup_match(preview_room())
        room = result.state
        assert room.match is not None and room.match.current_hand is not None
        hand = room.match.current_hand
        dealer_hand = hand_for_seat(room, SeatId("seat-0"))
        bonus_events = [
            event for event in result.domain_events if isinstance(event, BonusExposed)
        ]
        draw_events = [
            event for event in result.domain_events if isinstance(event, TileDrawn)
        ]

        self.assertGreater(MAX_AUTOMATED_CONTINUATIONS, 12)
        self.assertEqual(len(bonus_events), 12)
        self.assertTrue(all(not event.initial for event in bonus_events))
        self.assertEqual(len(dealer_hand.bonus_tiles), 12)
        self.assertEqual(
            {tile.tile_id for tile in dealer_hand.bonus_tiles},
            {event.tile.tile_id for event in bonus_events},
        )
        self.assertIsNotNone(dealer_hand.drawn_tile)
        assert dealer_hand.drawn_tile is not None
        self.assertFalse(is_bonus_tile(dealer_hand.drawn_tile))
        self.assertEqual(len(draw_events), 13)
        self.assertEqual(sum(event.replacement for event in draw_events), 12)
        self.assertEqual(len(hand.wall.live_tiles), 68)
        self.assertEqual(len(hand.wall.reserve_tiles), 15)
        self.assertEqual(len(canonical_locations(room)), 148)
        self.assertEqual(len(set(canonical_locations(room))), 148)

        replacement_ids = {
            event.tile.tile_id for event in draw_events if event.replacement
        }
        current_reserve_ids = {tile.tile_id for tile in hand.wall.reserve_tiles}
        self.assertTrue(replacement_ids.isdisjoint(current_reserve_ids))
        self.assertTrue(all(not is_bonus_tile(tile) for tile in hand.wall.reserve_tiles))
        validate_room(room)

    def test_initial_bonus_processing_is_dealer_relative_and_provenance_safe(self) -> None:
        result = SingaporeGameEngine(
            DealerTwoInitialBonusRandomSource()
        ).setup_match(preview_room())
        assert result.state.match is not None
        self.assertEqual(result.state.match.dealer_seat_id, SeatId("seat-2"))
        bonuses = [
            event for event in result.domain_events if isinstance(event, BonusExposed)
        ]
        self.assertEqual(
            [(event.seat_id, event.initial) for event in bonuses],
            [
                (SeatId("seat-2"), True),
                (SeatId("seat-2"), False),
                (SeatId("seat-2"), True),
                (SeatId("seat-3"), True),
                (SeatId("seat-0"), True),
                (SeatId("seat-1"), True),
            ],
        )
        all_initial_ids = {
            tile_id
            for slot in range(4)
            for tile_id in hand_for_seat(
                result.state, SeatId(f"seat-{slot}")
            ).initial_tile_ids
        }
        for event in bonuses:
            seat_initial_ids = set(
                hand_for_seat(result.state, event.seat_id).initial_tile_ids
            )
            if event.initial:
                self.assertIn(event.tile.tile_id, seat_initial_ids)
            else:
                self.assertNotIn(event.tile.tile_id, all_initial_ids)
        dealer_bonus_ids = tuple(
            tile.tile_id
            for tile in hand_for_seat(
                result.state, SeatId("seat-2")
            ).bonus_tiles
        )
        self.assertEqual(
            dealer_bonus_ids,
            tuple(event.tile.tile_id for event in bonuses[:3]),
        )
        winds = {
            seat.seat_id: seat.wind
            for seat in build_seat_observation(
                result.state, SeatId("seat-0")
            ).seats
        }
        self.assertEqual(
            winds,
            {
                SeatId("seat-0"): Wind.WEST,
                SeatId("seat-1"): Wind.NORTH,
                SeatId("seat-2"): Wind.EAST,
                SeatId("seat-3"): Wind.SOUTH,
            },
        )
        validate_room(result.state)
