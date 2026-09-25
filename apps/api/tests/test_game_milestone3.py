from __future__ import annotations

import json
import unittest
from collections import Counter
from typing import TypeVar

from pydantic import ValidationError

from app.game import (
    MAX_AUTOMATED_CONTINUATIONS,
    MILESTONE_3_CAPABILITIES,
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
    MilestoneThreeEngine,
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
    validate_milestone_three_room,
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
        ruleset_version="0.2.0",
        state_schema_version=3,
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
        result = MilestoneThreeEngine(source).setup_match(initial)
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
        validate_milestone_three_room(room)

    def test_raw_initial_provenance_keeps_exposed_bonus_not_replacement(self) -> None:
        source = InitialBonusRandomSource()
        result = MilestoneThreeEngine(source).setup_match(preview_room())
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
        validate_milestone_three_room(result.state)

    def test_all_twelve_bonuses_can_form_one_bounded_replacement_chain(self) -> None:
        source = AllBonusChainRandomSource()
        result = MilestoneThreeEngine(source).setup_match(preview_room())
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
        validate_milestone_three_room(room)

    def test_initial_bonus_processing_is_dealer_relative_and_provenance_safe(self) -> None:
        result = MilestoneThreeEngine(
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
        validate_milestone_three_room(result.state)


class DrawDiscardLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MilestoneThreeEngine(IdentityRandomSource())
        self.room = self.engine.setup_match(preview_room()).state
        assert self.room.match is not None
        self.dealer = self.room.match.dealer_seat_id
        assert self.dealer is not None

    def test_legal_catalog_has_both_discard_paths_and_no_draw_action(self) -> None:
        player_hand = hand_for_seat(self.room, self.dealer)
        actions = self.engine.legal_actions(self.room, self.dealer)

        self.assertEqual(len(actions), 14)
        self.assertTrue(all(isinstance(action, Discard) for action in actions))
        self.assertEqual(
            tuple(action.tile_id for action in actions[:-1]),
            tuple(tile.tile_id for tile in player_hand.concealed_tiles),
        )
        assert player_hand.drawn_tile is not None
        self.assertEqual(actions[-1].tile_id, player_hand.drawn_tile.tile_id)
        for other_slot in (1, 2, 3):
            self.assertEqual(
                self.engine.legal_actions(self.room, SeatId(f"seat-{other_slot}")),
                (),
            )

    def test_discarding_draw_buffer_preserves_concealed_hand(self) -> None:
        before = hand_for_seat(self.room, self.dealer)
        action = self.engine.legal_actions(self.room, self.dealer)[-1]
        result = self.engine.transition(self.room, action)
        after = hand_for_seat(result.state, self.dealer)
        assert before.drawn_tile is not None

        self.assertEqual(after.concealed_tiles, before.concealed_tiles)
        self.assertIsNone(after.drawn_tile)
        self.assertIsInstance(
            result.state.match.current_hand.phase,  # type: ignore[union-attr]
            DiscardClaimsPhase,
        )
        self.assertEqual(
            result.state.match.current_hand.discards[-1].tile,  # type: ignore[union-attr]
            before.drawn_tile,
        )
        self.assertIsInstance(result.domain_events[0], TileDiscarded)
        self.assertEqual(result.domain_events[0].discard_sequence, 1)
        self.assertEqual(len(result.effects), 1)
        self.assertIsInstance(result.effects[0], ClaimWindowRequested)
        self.assertEqual(result.effects[0].duration_ms, 3000)
        self.assertEqual(result.effects[0].eligible_seat_ids, ())

    def test_discarding_concealed_tile_merges_and_sorts_draw_buffer(self) -> None:
        before = hand_for_seat(self.room, self.dealer)
        selected = before.concealed_tiles[0]
        assert before.drawn_tile is not None
        action = self.engine.legal_actions(self.room, self.dealer)[0]
        result = self.engine.transition(self.room, action)
        after = hand_for_seat(result.state, self.dealer)

        self.assertIsNone(after.drawn_tile)
        self.assertNotIn(selected, after.concealed_tiles)
        self.assertIn(before.drawn_tile, after.concealed_tiles)
        self.assertEqual(
            after.concealed_tiles,
            sort_playable_tiles(after.concealed_tiles),
        )
        self.assertEqual(
            result.state.match.current_hand.discards[-1].tile,  # type: ignore[union-attr]
            selected,
        )

    def test_window_resolution_advances_counterclockwise_and_draws_automatically(self) -> None:
        discarded = self.engine.transition(
            self.room,
            self.engine.legal_actions(self.room, self.dealer)[-1],
        )
        assert discarded.state.match is not None
        assert discarded.state.match.current_hand is not None
        phase = discarded.state.match.current_hand.phase
        assert isinstance(phase, DiscardClaimsPhase)
        resolved = self.engine.resolve_discard_window(discarded.state, phase.window_id)
        hand = resolved.state.match.current_hand  # type: ignore[union-attr]
        assert hand is not None

        self.assertIsInstance(resolved.domain_events[0], DiscardWindowResolved)
        self.assertEqual(resolved.domain_events[0].window_id, phase.window_id)
        self.assertIsInstance(resolved.domain_events[1], TileDrawn)
        self.assertEqual(resolved.domain_events[1].seat_id, SeatId("seat-1"))
        self.assertIsInstance(hand.phase, AwaitingDiscardPhase)
        self.assertEqual(hand.phase.seat_id, SeatId("seat-1"))
        self.assertIsNotNone(hand_for_seat(resolved.state, SeatId("seat-1")).drawn_tile)
        self.assertEqual(
            resolved.effects,
            (AutomatedDecisionRequested(seat_id=SeatId("seat-1")),),
        )

    def test_forged_or_stale_actions_and_windows_are_generically_rejected(self) -> None:
        action = self.engine.legal_actions(self.room, self.dealer)[-1]
        discarded = self.engine.transition(self.room, action)
        with self.assertRaisesRegex(IllegalGameActionError, "action is not available"):
            self.engine.transition(self.room, Discard(seat_id=SeatId("seat-1"), tile_id=action.tile_id))
        with self.assertRaisesRegex(IllegalGameActionError, "action is not available"):
            self.engine.transition(discarded.state, action)
        with self.assertRaisesRegex(IllegalGameActionError, "action is not available"):
            self.engine.resolve_discard_window(
                discarded.state,
                WindowId("wrong-window"),
            )

    def test_window_state_serializes_only_after_room_persists_exact_deadline(self) -> None:
        discarded = self.engine.transition(
            self.room,
            self.engine.legal_actions(self.room, self.dealer)[-1],
        )
        assert discarded.state.match is not None
        assert discarded.state.match.current_hand is not None
        phase = discarded.state.match.current_hand.phase
        assert isinstance(phase, DiscardClaimsPhase)

        with self.assertRaises(InvalidGameStateError):
            serialize_room_state(discarded.state)

        values = discarded.state.model_dump()
        values["pending_deadline"] = PendingDeadline(
            window_id=phase.window_id,
            deadline_ms=3_200,
        )
        persisted = RoomState.model_validate(values)
        encoded = serialize_room_state(persisted)
        reconstructed = deserialize_room_state(encoded)
        self.assertEqual(reconstructed, persisted)
        self.assertEqual(json.loads(encoded)["pendingDeadline"]["deadlineMs"], 3200)

    def test_full_automatic_preview_conserves_tiles_and_finishes_on_last_live_draw(self) -> None:
        state = self.room
        final_transition = None
        for _ in range(148):
            assert state.match is not None and state.match.current_hand is not None
            hand = state.match.current_hand
            if isinstance(hand.phase, CompletePhase):
                break
            self.assertIsInstance(hand.phase, AwaitingDiscardPhase)
            active = hand.phase.seat_id
            legal = self.engine.legal_actions(state, active)
            action = choose_automated_action(
                state,
                active,
                legal,
                DeterministicRandomSource(f"discard-{len(hand.discards)}"),
            )
            discarded = self.engine.transition(state, action)
            assert discarded.state.match is not None
            assert discarded.state.match.current_hand is not None
            window_phase = discarded.state.match.current_hand.phase
            assert isinstance(window_phase, DiscardClaimsPhase)
            final_transition = self.engine.resolve_discard_window(
                discarded.state,
                window_phase.window_id,
            )
            state = final_transition.state
        else:  # pragma: no cover - explicit non-progress guard
            self.fail("preview did not reach live-wall exhaustion")

        assert final_transition is not None
        assert state.match is not None and state.match.current_hand is not None
        hand = state.match.current_hand
        self.assertIsInstance(hand.phase, CompletePhase)
        self.assertEqual(hand.result.outcome, HandOutcome.TIE)  # type: ignore[union-attr]
        self.assertEqual(hand.result.reason, "LIVE_WALL_EXHAUSTED")  # type: ignore[union-attr]
        self.assertEqual(len(hand.wall.live_tiles), 0)
        self.assertEqual(len(hand.wall.reserve_tiles), 15)
        self.assertEqual(len(canonical_locations(state)), 148)
        self.assertEqual(len(set(canonical_locations(state))), 148)
        self.assertEqual(
            [discard.sequence for discard in hand.discards],
            list(range(1, len(hand.discards) + 1)),
        )
        self.assertEqual(
            sum(isinstance(event, HandCompleted) for event in final_transition.domain_events),
            1,
        )
        self.assertEqual(final_transition.effects, (MatchCompletionRequested(),))

        validate_milestone_three_room(state)
        with self.assertRaisesRegex(
            InvalidGameStateError,
            "finalized before persistence",
        ):
            serialize_room_state(state)

        finalized = finalize_completed_preview(state, completed_at_ms=9_999)
        assert finalized.match is not None
        self.assertEqual(finalized.status, RoomStatus.FINISHED)
        self.assertEqual(finalized.match.status, MatchStatus.FINISHED)
        self.assertEqual(finalized.match.current_hand, hand)
        self.assertEqual(finalized.match.hand_history, (hand.result,))
        self.assertEqual(finalized.match.result.completed_at_ms, 9_999)  # type: ignore[union-attr]
        self.assertEqual(finalized.match.result.winning_seat_ids, ())  # type: ignore[union-attr]
        self.assertTrue(
            all(balance.points == 0 for balance in finalized.match.result.final_balances)  # type: ignore[union-attr]
        )
        self.assertEqual(
            finalize_completed_preview(finalized, completed_at_ms=10_000),
            finalized,
        )
        self.assertEqual(deserialize_room_state(serialize_room_state(finalized)), finalized)

        invalid_result = hand.result.model_copy(update={"fan": 1})  # type: ignore[union-attr]
        invalid_hand = hand.model_copy(update={"result": invalid_result})
        invalid_match = state.match.model_copy(update={"current_hand": invalid_hand})
        with self.assertRaisesRegex(InvalidGameStateError, "unscored wall tie"):
            validate_milestone_three_room(
                state.model_copy(update={"match": invalid_match})
            )

        forged_history_match = state.match.model_copy(
            update={"hand_history": (hand.result,)}
        )
        with self.assertRaisesRegex(InvalidGameStateError, "active preview"):
            finalize_completed_preview(
                state.model_copy(update={"match": forged_history_match}),
                completed_at_ms=10_000,
            )

        duplicated_history = finalized.match.model_copy(
            update={"hand_history": (hand.result, hand.result)}
        )
        with self.assertRaisesRegex(InvalidGameStateError, "exactly"):
            validate_milestone_three_room(
                finalized.model_copy(update={"match": duplicated_history})
            )

        invalid_match_result = finalized.match.result.model_copy(  # type: ignore[union-attr]
            update={"winning_seat_ids": (SeatId("seat-0"),)}
        )
        changed_finished_match = finalized.match.model_copy(
            update={"result": invalid_match_result}
        )
        with self.assertRaisesRegex(InvalidGameStateError, "match result"):
            validate_milestone_three_room(
                finalized.model_copy(update={"match": changed_finished_match})
            )

    def test_final_live_bonus_is_exposed_and_retained_without_a_replacement(self) -> None:
        source = FinalLiveBonusRandomSource()
        engine = MilestoneThreeEngine(source)
        state = engine.setup_match(preview_room()).state
        final_transition = None
        for _ in range(100):
            assert state.match is not None and state.match.current_hand is not None
            hand = state.match.current_hand
            if isinstance(hand.phase, CompletePhase):
                break
            assert isinstance(hand.phase, AwaitingDiscardPhase)
            discarded = engine.transition(
                state,
                engine.legal_actions(state, hand.phase.seat_id)[-1],
            )
            window = discarded.state.match.current_hand.phase  # type: ignore[union-attr]
            assert isinstance(window, DiscardClaimsPhase)
            final_transition = engine.resolve_discard_window(
                discarded.state,
                window.window_id,
            )
            state = final_transition.state
        else:  # pragma: no cover - explicit non-progress guard
            self.fail("final-bonus preview did not terminate")

        assert source.final_bonus is not None and final_transition is not None
        assert state.match is not None and state.match.current_hand is not None
        hand = state.match.current_hand
        exposed = [
            event
            for event in final_transition.domain_events
            if isinstance(event, BonusExposed)
        ]
        self.assertIsInstance(hand.phase, CompletePhase)
        self.assertEqual(exposed[0].tile.face, source.final_bonus.face)  # type: ignore[attr-defined]
        self.assertEqual(len(exposed), 1)
        self.assertIsNone(
            hand_for_seat(state, exposed[0].seat_id).drawn_tile
        )
        self.assertIn(
            exposed[0].tile,
            hand_for_seat(state, exposed[0].seat_id).bonus_tiles,
        )
        self.assertEqual(
            sum(isinstance(event, HandCompleted) for event in final_transition.domain_events),
            1,
        )
        self.assertEqual(len(canonical_locations(state)), 148)
        validate_milestone_three_room(state)


class ObservationProjectionAndInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MilestoneThreeEngine(IdentityRandomSource())
        self.room = self.engine.setup_match(preview_room(human_at_zero=True)).state

    def test_seat_observations_keep_only_own_physical_ids(self) -> None:
        human = build_seat_observation(
            self.room,
            SeatId("seat-0"),
            viewer_player_id=PlayerId("player-0"),
        )
        bot = build_seat_observation(self.room, SeatId("seat-1"))
        own = human.seats[0]
        opponent = human.seats[1]

        self.assertEqual(human.capabilities, MILESTONE_3_CAPABILITIES)
        self.assertEqual(human.viewer_seat_id, SeatId("seat-0"))
        self.assertEqual(human.viewer_player_id, PlayerId("player-0"))
        self.assertTrue(hasattr(own, "concealed_tiles"))
        self.assertIsInstance(opponent, OpponentSeatObservation)
        self.assertFalse(hasattr(opponent, "concealed_tiles"))
        encoded = human.canonical_json()
        salt = self.room.match.current_hand.tile_id_salt  # type: ignore[union-attr]
        self.assertNotIn("tileIdSalt", encoded)
        self.assertNotIn(salt, encoded)  # type: ignore[arg-type]
        for tile in hand_for_seat(self.room, SeatId("seat-0")).concealed_tiles:
            self.assertIn(str(tile.tile_id), encoded)
        for tile in hand_for_seat(self.room, SeatId("seat-1")).concealed_tiles:
            self.assertNotIn(str(tile.tile_id), encoded)
        self.assertEqual(bot.viewer_seat_id, SeatId("seat-1"))
        self.assertIsNone(bot.viewer_player_id)

    def test_public_projection_is_face_only_even_for_self(self) -> None:
        view = build_public_room_view(
            self.room,
            PlayerId("player-0"),
            server_time_ms=250,
        )
        encoded = view.canonical_json()
        self.assertEqual(view.capabilities, MILESTONE_3_CAPABILITIES)
        self.assertNotIn('"tileId"', encoded)
        salt = self.room.match.current_hand.tile_id_salt  # type: ignore[union-attr]
        self.assertNotIn("tileIdSalt", encoded)
        self.assertNotIn(salt, encoded)  # type: ignore[arg-type]
        self.assertNotIn(str(self.room.match.current_hand.wall.live_tiles[0].tile_id), encoded)  # type: ignore[union-attr]
        self.assertIsInstance(view.seats[0], SelfSeatView)
        self.assertIsInstance(view.seats[0].concealed_tiles[0], PublicTileView)
        self.assertFalse(hasattr(view.seats[0].concealed_tiles[0], "tile_id"))
        self.assertIsInstance(view.seats[1], OpponentSeatView)
        self.assertFalse(hasattr(view.seats[1], "concealed_tiles"))

    def test_action_descriptors_bind_concealed_indices_or_draw_buffer_only(self) -> None:
        concealed = OpaqueActionDescriptor(
            action_id="opaque-concealed",
            label="Discard 1 Characters",
            presentation_slot="concealedTile",
            presentation_index=0,
        )
        drawn = OpaqueActionDescriptor(
            action_id="opaque-drawn",
            label="Discard Red Dragon",
            presentation_slot="drawnTile",
        )
        self.assertEqual(concealed.presentation_index, 0)
        self.assertIsNone(drawn.presentation_index)
        for invalid in (
            {
                "actionId": "missing-index",
                "label": "Discard",
                "presentationSlot": "concealedTile",
            },
            {
                "actionId": "unexpected-index",
                "label": "Discard",
                "presentationSlot": "drawnTile",
                "presentationIndex": 0,
            },
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                OpaqueActionDescriptor.model_validate(invalid)

    def test_projection_deadline_is_derived_only_from_canonical_state(self) -> None:
        assert self.room.match is not None
        dealer = self.room.match.dealer_seat_id
        assert dealer is not None
        discarded = self.engine.transition(
            self.room,
            self.engine.legal_actions(self.room, dealer)[-1],
        )
        assert discarded.state.match is not None
        assert discarded.state.match.current_hand is not None
        phase = discarded.state.match.current_hand.phase
        assert isinstance(phase, DiscardClaimsPhase)
        values = discarded.state.model_dump()
        values["pending_deadline"] = PendingDeadline(
            window_id=phase.window_id,
            deadline_ms=3_250,
        )
        canonical = RoomState.model_validate(values)
        view = build_public_room_view(
            canonical,
            PlayerId("player-0"),
            server_time_ms=300,
        )
        self.assertEqual(view.deadline_ms, 3_250)
        self.assertEqual(view.window_id, phase.window_id)
        with self.assertRaisesRegex(ValueError, "canonical room state"):
            build_public_room_view(
                canonical,
                PlayerId("player-0"),
                server_time_ms=300,
                deadline_ms=3_251,
            )
        with self.assertRaisesRegex(ValueError, "canonical room state"):
            build_public_room_view(
                canonical,
                PlayerId("player-0"),
                server_time_ms=300,
                window_id=WindowId("forged-window"),
            )

    def test_random_bot_selects_only_from_its_legal_discard_catalog(self) -> None:
        all_bot = MilestoneThreeEngine(IdentityRandomSource()).setup_match(
            preview_room()
        ).state
        actions = self.engine.legal_actions(all_bot, SeatId("seat-0"))
        left = choose_automated_action(
            all_bot,
            SeatId("seat-0"),
            actions,
            DeterministicRandomSource("bot-choice"),
        )
        right = choose_automated_action(
            all_bot,
            SeatId("seat-0"),
            actions,
            DeterministicRandomSource("bot-choice"),
        )
        self.assertEqual(left, right)
        self.assertIn(left, actions)
        self.assertIsInstance(left, Discard)

    def test_validator_rejects_canonical_tile_identity_corruption(self) -> None:
        assert self.room.match is not None and self.room.match.current_hand is not None
        hand = self.room.match.current_hand
        first = hand.wall.live_tiles[0]
        changed_tile = first.model_copy(
            update={"face": TileFace(family=TileFamily.DRAGON, value="RED")}
        )
        changed_wall = hand.wall.model_copy(
            update={"live_tiles": (changed_tile, *hand.wall.live_tiles[1:])}
        )
        changed_hand = hand.model_copy(update={"wall": changed_wall})
        changed_match = self.room.match.model_copy(update={"current_hand": changed_hand})
        corrupted = self.room.model_copy(update={"match": changed_match})
        with self.assertRaisesRegex(InvalidGameStateError, "canonical deck"):
            validate_milestone_three_room(corrupted)

    def test_validator_rejects_forged_initial_provenance_in_wall_or_draw(self) -> None:
        assert self.room.match is not None and self.room.match.current_hand is not None
        hand = self.room.match.current_hand
        wall_ids = tuple(
            tile.tile_id
            for tile in (*hand.wall.live_tiles, *hand.wall.reserve_tiles)
        )
        changed_hands = tuple(
            player_hand.model_copy(
                update={
                    "initial_tile_ids": wall_ids[index * 13 : (index + 1) * 13]
                }
            )
            for index, player_hand in enumerate(hand.player_hands)
        )
        changed_hand = hand.model_copy(update={"player_hands": changed_hands})
        changed_match = self.room.match.model_copy(update={"current_hand": changed_hand})
        with self.assertRaisesRegex(InvalidGameStateError, "not attributable"):
            validate_milestone_three_room(
                self.room.model_copy(update={"match": changed_match})
            )

        dealer_hand = hand_for_seat(self.room, SeatId("seat-0"))
        assert dealer_hand.drawn_tile is not None
        forged_ids = (
            dealer_hand.drawn_tile.tile_id,
            *dealer_hand.initial_tile_ids[1:],
        )
        forged_dealer = dealer_hand.model_copy(
            update={"initial_tile_ids": forged_ids}
        )
        draw_changed_hand = hand.model_copy(
            update={
                "player_hands": tuple(
                    forged_dealer if value.seat_id == SeatId("seat-0") else value
                    for value in hand.player_hands
                )
            }
        )
        draw_changed_match = self.room.match.model_copy(
            update={"current_hand": draw_changed_hand}
        )
        with self.assertRaisesRegex(InvalidGameStateError, "not attributable"):
            validate_milestone_three_room(
                self.room.model_copy(update={"match": draw_changed_match})
            )

    def test_validator_rejects_bonus_discards_and_impossible_turn_ledger(self) -> None:
        assert self.room.match is not None
        dealer = self.room.match.dealer_seat_id
        assert dealer is not None
        first = self.engine.transition(
            self.room,
            self.engine.legal_actions(self.room, dealer)[-1],
        ).state
        assert first.match is not None and first.match.current_hand is not None
        first_hand = first.match.current_hand
        bonus_index = next(
            index
            for index, tile in enumerate(first_hand.wall.reserve_tiles)
            if is_bonus_tile(tile)
        )
        bonus = first_hand.wall.reserve_tiles[bonus_index]
        discarded_regular = first_hand.discards[0].tile
        changed_reserve = list(first_hand.wall.reserve_tiles)
        changed_reserve[bonus_index] = discarded_regular
        changed_wall = first_hand.wall.model_copy(
            update={"reserve_tiles": tuple(changed_reserve)}
        )
        changed_discard = first_hand.discards[0].model_copy(update={"tile": bonus})
        bonus_hand = first_hand.model_copy(
            update={"wall": changed_wall, "discards": (changed_discard,)}
        )
        bonus_match = first.match.model_copy(update={"current_hand": bonus_hand})
        with self.assertRaisesRegex(InvalidGameStateError, "cannot be discarded"):
            validate_milestone_three_room(
                first.model_copy(update={"match": bonus_match})
            )

        phase = first_hand.phase
        assert isinstance(phase, DiscardClaimsPhase)
        second_draw = self.engine.resolve_discard_window(first, phase.window_id).state
        second = self.engine.transition(
            second_draw,
            self.engine.legal_actions(second_draw, SeatId("seat-1"))[-1],
        ).state
        assert second.match is not None and second.match.current_hand is not None
        second_hand = second.match.current_hand
        impossible_second = second_hand.discards[1].model_copy(
            update={"discarded_by_seat_id": SeatId("seat-0")}
        )
        impossible_hand = second_hand.model_copy(
            update={"discards": (second_hand.discards[0], impossible_second)}
        )
        impossible_match = second.match.model_copy(
            update={"current_hand": impossible_hand}
        )
        with self.assertRaisesRegex(InvalidGameStateError, "cyclic seat order"):
            validate_milestone_three_room(
                second.model_copy(update={"match": impossible_match})
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
