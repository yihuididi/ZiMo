from __future__ import annotations

import itertools
import unittest

from app.game import (
    Chow,
    Discard,
    FinishHand,
    Kong,
    KongKind,
    Pass,
    Pong,
    ClaimKind,
    PendingClaim,
    CompletePhase,
    DiscardClaimsPhase,
    FinalTileDecisionPhase,
    AwaitingDrawPhase,
    MilestoneFourEngine,
    DeterministicRandomSource,
    RandomBotPolicy,
    RoomState,
    SeatId,
    WindowId,
    PendingDeadline,
    build_seat_observation,
    build_public_room_view,
    validate_milestone_four_room,
    finalize_completed_preview,
    serialize_room_state,
    deserialize_room_state,
    IllegalGameActionError,
)
from app.game.claims import winning_claim
from app.game.milestone4 import _updated
from app.game.engine import _room_with_hand
from test_game_milestone3 import (
    preview_room,
    IdentityRandomSource,
    AllBonusChainRandomSource,
)


class ArrangedDeck(IdentityRandomSource):
    """A real 148-tile permutation, with selected ranks dealt to selected seats."""

    def __init__(self, hands=None, draw=5):
        self.hands = hands or {1: [3, 4, 6, 7], 2: [5, 5]}
        self.draw = draw

    def shuffled(self, values):
        remaining = list(values)

        def take(rank):
            tile = next(
                t
                for t in remaining
                if t.face.family.value == "BAMBOO" and t.face.value == rank
            )
            remaining.remove(tile)
            return tile

        desired = {
            seat: [take(rank) for rank in ranks] for seat, ranks in self.hands.items()
        }
        draw = take(self.draw)
        # Fill with other suits to avoid accidental extra copies of target faces.
        filler = [t for t in remaining if t.face.family.value in {"CHARACTERS", "DOTS"}]
        for seat in range(4):
            desired.setdefault(seat, [])
            while len(desired[seat]) < 13:
                tile = filler.pop(0)
                remaining.remove(tile)
                desired[seat].append(tile)
        raw = [desired[seat][i] for i in range(13) for seat in range(4)]
        return (*raw, draw, *remaining)


def started(rng=None):
    room = preview_room(human_at_zero=True).model_copy(
        update={"ruleset_version": "0.3.0", "state_schema_version": 4}
    )
    engine = MilestoneFourEngine(rng or ArrangedDeck())
    return engine, engine.setup_match(room).state


def discard_draw(engine, state):
    hand = state.match.current_hand
    player = next(p for p in hand.player_hands if p.seat_id == hand.phase.seat_id)
    return engine.transition(
        state, Discard(seat_id=player.seat_id, tile_id=player.drawn_tile.tile_id)
    ).state


class ClaimTests(unittest.TestCase):
    def test_three_chows_only_next_seat_and_pong_priority_independent_of_arrival(self):
        engine, state = started()
        state = discard_draw(engine, state)
        chow_actions = [
            a
            for a in engine.legal_actions(state, SeatId("seat-1"))
            if isinstance(a, Chow)
        ]
        self.assertEqual(len(chow_actions), 3)
        self.assertFalse(
            any(
                isinstance(a, Chow)
                for a in engine.legal_actions(state, SeatId("seat-2"))
            )
        )
        pong = next(
            a
            for a in engine.legal_actions(state, SeatId("seat-2"))
            if isinstance(a, Pong)
        )
        results = []
        for actions in itertools.permutations((chow_actions[0], pong)):
            pending = state
            for action in actions:
                before = pending.match.current_hand
                pending = engine.transition(pending, action).state
                self.assertEqual(
                    pending.match.current_hand.player_hands, before.player_hands
                )
                self.assertEqual(pending.match.current_hand.discards, before.discards)
            resolved = engine.resolve_discard_window(
                pending, pending.match.current_hand.phase.window_id
            )
            results.append(resolved.state.canonical_json())
            hand = resolved.state.match.current_hand
            self.assertEqual(str(hand.phase.seat_id), "seat-2")
            self.assertIsNone(hand.player_hands[2].drawn_tile)
            self.assertEqual(hand.player_hands[2].melds[0].discard_sequence, 1)
            self.assertEqual(str(hand.discards[0].claimed_by_seat_id), "seat-2")
            self.assertTrue(
                all(
                    isinstance(a, Discard)
                    for a in engine.legal_actions(resolved.state, SeatId("seat-2"))
                )
            )
            engine.transition(
                resolved.state,
                engine.legal_actions(resolved.state, SeatId("seat-2"))[0],
            )
        self.assertEqual(results[0], results[1])

    def test_claim_is_final_and_private(self):
        engine, state = started()
        state = discard_draw(engine, state)
        action = engine.legal_actions(state, SeatId("seat-2"))[0]
        state = engine.transition(state, action).state
        self.assertEqual(engine.legal_actions(state, SeatId("seat-2")), ())
        with self.assertRaises(IllegalGameActionError):
            engine.transition(state, action)
        observation = build_seat_observation(state, SeatId("seat-1"))
        self.assertEqual(observation.match.own_pending_claims, ())
        public = build_public_room_view(
            state, state.players[0].player_id, server_time_ms=100
        )
        self.assertNotIn("tileId", public.canonical_json())
        self.assertNotIn("pendingClaims", public.canonical_json())
        self.assertFalse(public.game.own_claim_submitted)

    def test_equal_priority_uses_counterclockwise_seating(self):
        seats = tuple(SeatId(f"seat-{i}") for i in range(4))
        for discarder in seats:
            nearest = seats[(seats.index(discarder) + 1) % 4]
            others = [s for s in seats if s != discarder]
            claims = tuple(
                PendingClaim(
                    window_id=WindowId("w"),
                    seat_id=s,
                    kind=ClaimKind.PONG,
                    tile_ids=(f"{s}-a", f"{s}-b"),
                )
                for s in others
            )
            for ordering in itertools.permutations(claims):
                self.assertEqual(
                    winning_claim(ordering, seats, discarder).seat_id, nearest
                )
            kong = claims[1].model_copy(
                update={"kind": ClaimKind.KONG, "tile_ids": ("a", "b", "c")}
            )
            self.assertEqual(
                winning_claim((kong, claims[0]), seats, discarder).seat_id,
                min(
                    (kong, claims[0]),
                    key=lambda c: (seats.index(c.seat_id) - seats.index(discarder)) % 4,
                ).seat_id,
            )

    def test_passed_pong_and_own_last_discard_restrictions(self):
        engine, state = started()
        state = discard_draw(engine, state)
        face = state.match.current_hand.discards[-1].tile.face
        player = state.match.current_hand.player_hands[2]
        for changes in ({"passed_pong_faces": (face,)}, {"last_discard_face": face}):
            hand = state.match.current_hand
            changed_player = _updated(player, **changes)
            hand = _updated(
                hand,
                player_hands=tuple(
                    changed_player if p.seat_id == player.seat_id else p
                    for p in hand.player_hands
                ),
            )
            changed = _room_with_hand(state, hand, pending_deadline=None)
            self.assertFalse(
                any(
                    isinstance(a, Pong)
                    for a in engine.legal_actions(changed, player.seat_id)
                )
            )
        # Timeout declines seat 2's Pong; seat 1 draws, so only seat 1 resets.
        resolved = engine.resolve_discard_window(
            state, state.match.current_hand.phase.window_id
        ).state
        self.assertIn(
            face, resolved.match.current_hand.player_hands[2].passed_pong_faces
        )
        self.assertEqual(
            resolved.match.current_hand.player_hands[1].passed_pong_faces, ()
        )

    def test_claimed_kong_replaces_and_keeps_historical_reference(self):
        engine, state = started(ArrangedDeck({2: [5, 5, 5]}))
        state = discard_draw(engine, state)
        kong = next(
            a
            for a in engine.legal_actions(state, SeatId("seat-2"))
            if isinstance(a, Kong)
        )
        state = engine.transition(state, kong).state
        state = engine.resolve_discard_window(
            state, state.match.current_hand.phase.window_id
        ).state
        player = state.match.current_hand.player_hands[2]
        self.assertEqual(player.melds[0].kong_kind, "KONG_3")
        self.assertIsNotNone(player.drawn_tile)
        self.assertEqual(len(player.concealed_tiles), 10)
        self.assertIn(state.match.current_hand.discards[0].tile, player.melds[0].tiles)
        validate_milestone_four_room(state)

    def test_multiple_concealed_kongs_and_unconsumed_draw_buffer(self):
        engine, state = started(ArrangedDeck({0: [1] * 4 + [2] * 4}, draw=5))
        kongs = [
            a
            for a in engine.legal_actions(state, SeatId("seat-0"))
            if isinstance(a, Kong)
        ]
        self.assertGreaterEqual(len(kongs), 2)
        old_draw = state.match.current_hand.player_hands[0].drawn_tile
        state = engine.transition(state, kongs[0]).state
        player = state.match.current_hand.player_hands[0]
        self.assertIn(old_draw, player.concealed_tiles)
        self.assertFalse(player.melds[0].concealed)
        self.assertEqual(player.melds[0].kong_kind, "KONG_4")
        self.assertEqual(len(player.concealed_tiles), 10)
        self.assertEqual(len(state.match.current_hand.wall.reserve_tiles), 15)
        self.assertTrue(
            any(
                isinstance(a, Kong) for a in engine.legal_actions(state, player.seat_id)
            )
        )

    def test_all_bonus_chain_and_no_unsupported_actions(self):
        engine, state = started(AllBonusChainRandomSource())
        self.assertEqual(len(state.match.current_hand.player_hands[0].bonus_tiles), 12)
        self.assertTrue(
            all(
                a.type in {"discard", "kong"}
                for a in engine.legal_actions(state, SeatId("seat-0"))
            )
        )
        self.assertTrue(
            all(
                not isinstance(a, Kong) or a.kind is KongKind.CONCEALED
                for a in engine.legal_actions(state, SeatId("seat-0"))
            )
        )

    def test_final_tile_kong_or_finish_without_replacement(self):
        engine, state = started(ArrangedDeck({0: [1] * 4}, draw=5))
        hand = state.match.current_hand
        from app.game import DiscardState

        extra = tuple(
            DiscardState(sequence=i + 1, tile=t, discarded_by_seat_id=SeatId("seat-1"))
            for i, t in enumerate(hand.wall.live_tiles)
            if t.face.family.value not in {"FLOWER", "SEASON", "ANIMAL"}
        )
        bonus = tuple(
            t
            for t in hand.wall.live_tiles
            if t.face.family.value in {"FLOWER", "SEASON", "ANIMAL"}
        )
        player = _updated(
            hand.player_hands[1],
            bonus_tiles=(*hand.player_hands[1].bonus_tiles, *bonus),
            last_discard_face=extra[-1].tile.face,
        )
        hand = _updated(
            hand,
            discards=extra,
            wall=_updated(hand.wall, live_tiles=()),
            player_hands=tuple(
                player if p.seat_id == player.seat_id else p for p in hand.player_hands
            ),
            phase=FinalTileDecisionPhase(seat_id=SeatId("seat-0")),
        )
        # Feed the final tile through the real draw path, not just the phase model.
        actor = hand.player_hands[0]
        hand = _updated(
            hand,
            phase=AwaitingDrawPhase(seat_id=actor.seat_id),
            wall=_updated(hand.wall, live_tiles=(actor.drawn_tile,)),
            player_hands=(_updated(actor, drawn_tile=None), *hand.player_hands[1:]),
        )
        state = engine._automatic_draw(
            _room_with_hand(state, hand, pending_deadline=None), actor.seat_id
        ).state
        hand = state.match.current_hand
        self.assertIsInstance(hand.phase, FinalTileDecisionPhase)
        validate_milestone_four_room(state)
        self.assertEqual(deserialize_room_state(serialize_room_state(state)), state)
        for action in engine.legal_actions(state, SeatId("seat-0")):
            result = engine.transition(state, action)
            final = result.state.match.current_hand
            self.assertIsInstance(final.phase, CompletePhase)
            self.assertEqual(final.wall.reserve_tiles, hand.wall.reserve_tiles)
            self.assertEqual(final.discards, hand.discards)
            self.assertFalse(any(e.type == "tileDrawn" for e in result.domain_events))

    def test_seeded_full_hands_never_deadlock(self):
        for seed in range(8):
            engine, state = started(DeterministicRandomSource(str(seed)))
            policy = RandomBotPolicy()
            rng = DeterministicRandomSource(f"policy-{seed}")
            for _ in range(700):
                hand = state.match.current_hand
                validate_milestone_four_room(state)
                if isinstance(hand.phase, CompletePhase):
                    final = finalize_completed_preview(state, completed_at_ms=10000)
                    self.assertEqual(
                        deserialize_room_state(serialize_room_state(final)), final
                    )
                    break
                if isinstance(hand.phase, DiscardClaimsPhase):
                    for seat in hand.phase.eligible_seat_ids:
                        actions = engine.legal_actions(state, seat)
                        state = engine.transition(
                            state,
                            policy.choose_action(
                                build_seat_observation(state, seat), actions, rng
                            ),
                        ).state
                    state = engine.resolve_discard_window(
                        state, hand.phase.window_id
                    ).state
                else:
                    seat = hand.phase.seat_id
                    state = engine.transition(
                        state,
                        policy.choose_action(
                            build_seat_observation(state, seat),
                            engine.legal_actions(state, seat),
                            rng,
                        ),
                    ).state
            else:
                self.fail("seeded hand did not finish")
