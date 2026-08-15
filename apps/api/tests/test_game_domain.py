from __future__ import annotations

import json
import unittest

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.game import (
    AutomatedDecisionRequested,
    AutomatedSeatController,
    AwaitingDiscardPhase,
    AwaitingDrawPhase,
    Chow,
    ClaimKind,
    ClaimSubmitted,
    ClaimWindowRequested,
    CompletePhase,
    Continue,
    DeclareWin,
    Discard,
    DiscardClaimsPhase,
    DiscardState,
    DomainEffect,
    DomainEvent,
    DomainId,
    Draw,
    ExternalSeatController,
    GameConfig,
    GameplayUnavailableError,
    HandCompleted,
    HandId,
    HandOutcome,
    HandPhase,
    HandResult,
    HandSetupCompleted,
    HandState,
    Kong,
    KongDeclared,
    KongKind,
    KongReplacementPhase,
    KongRobberyPhase,
    MatchId,
    MatchState,
    MeldDeclared,
    MeldKind,
    MeldState,
    OpponentSeatObservation,
    OpponentSeatView,
    OwnSeatObservation,
    Pass,
    Payment,
    PendingClaim,
    PhysicalTile,
    PlayerHand,
    PlayerId,
    PublicConcealedMeldView,
    PublicExposedMeldView,
    PublicMeldView,
    PublicSeatView,
    PublicTileView,
    Pong,
    RoomId,
    RoomState,
    SeatController,
    SeatBalance,
    SeatId,
    SeatObservation,
    SelfSeatView,
    SetupPhase,
    SingaporeRules,
    TileDiscarded,
    TileDrawn,
    TileFace,
    TileFamily,
    TileId,
    UnsupportedConfigurationError,
    WallState,
    WinDeclared,
    WinSource,
    WindowId,
    canonical_json,
    deserialize_room_state,
    legal_actions,
    parse_domain_action_json,
    parse_domain_effect_json,
    parse_domain_event_json,
    standard_seats,
    transition,
)


def tile(tile_id: str = "tile-1") -> PhysicalTile:
    return PhysicalTile(
        tile_id=TileId(tile_id),
        face=TileFace(family=TileFamily.BAMBOO, value=1),
    )


class GameConfigTests(unittest.TestCase):
    def test_full_defaults(self) -> None:
        config = GameConfig()
        self.assertFalse(config.shooter_mode)
        self.assertEqual((config.minimum_fan, config.maximum_fan), (1, 5))
        self.assertEqual(config.payout_table, (1, 2, 4, 8, 16, 32))
        self.assertEqual(config.kong_one_payment, 2)
        self.assertEqual(config.kong_three_payment, 2)
        self.assertEqual(config.complete_animal_set_payment, 4)
        self.assertEqual(config.complete_flower_set_payment, 4)
        self.assertEqual(config.complete_season_set_payment, 4)
        self.assertEqual(config.animal_pair_payment, 2)
        self.assertEqual(config.flower_season_pair_payment, 2)
        self.assertEqual(config.initial_thirteen_pair_payment, 4)
        self.assertEqual(config.fresh_discard_threshold, 4)
        self.assertEqual(config.fresh_kong_threshold, 7)
        self.assertFalse(config.seven_pairs_enabled)
        self.assertFalse(config.fresh_kong_pay_all_enabled)
        self.assertFalse(config.kong_four_robbery_enabled)
        self.assertFalse(config.concealed_self_draw_bonus_enabled)
        self.assertTrue(config.automatic_dragon_wins_enabled)
        self.assertTrue(config.automatic_wind_wins_enabled)
        self.assertEqual(config.extra_self_draw_points, 0)

    def test_config_is_strict_frozen_and_forbids_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            GameConfig.model_validate({"surprise": True})
        with self.assertRaises(ValidationError):
            GameConfig.model_validate({"minimumFan": "1"})
        with self.assertRaises(ValidationError):
            GameConfig().minimum_fan = 2  # type: ignore[misc]

    def test_rejects_inconsistent_or_non_positive_payouts(self) -> None:
        invalid_values = (
            {"minimum_fan": 5, "maximum_fan": 4, "payout_table": (1, 2, 4, 8, 16)},
            {"payout_table": (1, 2)},
            {"payout_table": (1, 2, 4, 0, 16, 32)},
            {"payout_table": (1, 2, 4, 3, 16, 32)},
            {"kong_one_payment": 0},
            {"initial_thirteen_pair_payment": 1},
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                GameConfig.model_validate(value)

    def test_singapore_metadata_and_capability_gate(self) -> None:
        rules = SingaporeRules()
        self.assertEqual(rules.ruleset_id, "singapore")
        self.assertEqual(rules.ruleset_version, "0.1.0")
        self.assertEqual(rules.state_schema_version, 1)
        self.assertEqual(rules.seat_count, 4)
        self.assertEqual(rules.tile_count, 148)
        self.assertEqual(rules.reserve_tile_count, 15)
        self.assertEqual(rules.claim_window_ms, 3000)
        self.assertEqual(rules.capabilities, ())
        self.assertEqual(rules.configurable_fields, ())

    def test_rules_reject_future_config_until_a_capability_enables_it(self) -> None:
        rules = SingaporeRules()
        self.assertEqual(rules.normalize_config(GameConfig()), GameConfig())
        future_config = GameConfig(shooter_mode=True)
        self.assertTrue(future_config.shooter_mode)
        with self.assertRaises(UnsupportedConfigurationError):
            rules.normalize_config(future_config)
        with self.assertRaises(UnsupportedConfigurationError):
            rules.normalize_config(
                {
                    **GameConfig().model_dump(),
                    "seven_pairs_enabled": True,
                }
            )

    def test_milestone_capabilities_cannot_be_overridden(self) -> None:
        with self.assertRaises(ValidationError):
            SingaporeRules.model_validate({"capabilities": ("draw",)})
        with self.assertRaises(ValidationError):
            SingaporeRules.model_validate({"configurable_fields": ("shooterMode",)})

    def test_room_snapshot_cannot_bypass_config_capability_gate(self) -> None:
        with self.assertRaises(ValidationError):
            RoomState(
                room_id=RoomId("room-config-bypass"),
                config=GameConfig(shooter_mode=True),
                seats=standard_seats(),
                created_at_ms=0,
                updated_at_ms=0,
            )
        valid = RoomState(
            room_id=RoomId("room-copy-bypass"),
            seats=standard_seats(),
            created_at_ms=0,
            updated_at_ms=0,
        )
        unvalidated_copy = valid.model_copy(
            update={"config": GameConfig(shooter_mode=True)}
        )
        with self.assertRaises(ValueError):
            unvalidated_copy.canonical_json()
        with self.assertRaises(ValueError):
            canonical_json(unvalidated_copy)

    def test_exported_canonical_json_supports_non_domain_models(self) -> None:
        class OrdinaryModel(BaseModel):
            value: int

        self.assertEqual(canonical_json(OrdinaryModel(value=3)), '{"value":3}')


class BrandedIdentityTests(unittest.TestCase):
    def test_ids_are_distinct_immutable_string_brands(self) -> None:
        room_id = RoomId("same-text")
        player_id = PlayerId("same-text")
        self.assertIsInstance(room_id, DomainId)
        self.assertIsInstance(room_id, str)
        self.assertIs(type(room_id), RoomId)
        self.assertIs(type(player_id), PlayerId)
        self.assertNotEqual(room_id, player_id)
        self.assertNotEqual(player_id, room_id)
        self.assertNotEqual(room_id, "same-text")
        self.assertNotEqual("same-text", room_id)
        self.assertEqual(len({room_id, player_id, "same-text"}), 3)
        self.assertEqual(len({room_id, RoomId("same-text")}), 1)
        self.assertEqual(hash(room_id), hash(RoomId("same-text")))
        self.assertNotEqual(hash(room_id), hash(player_id))
        with self.assertRaises(TypeError):
            RoomId(player_id)  # type: ignore[arg-type]

    def test_pydantic_rejects_cross_type_ids(self) -> None:
        with self.assertRaises(ValidationError):
            RoomState(
                room_id=PlayerId("player-not-room"),  # type: ignore[arg-type]
                seats=standard_seats(),
                created_at_ms=0,
                updated_at_ms=0,
            )
        with self.assertRaises(ValidationError):
            ExternalSeatController(
                player_id=SeatId("seat-not-player")  # type: ignore[arg-type]
            )

    def test_ids_parse_from_json_as_brands_but_serialize_as_strings(self) -> None:
        room = RoomState(
            room_id=RoomId("room-branded"),
            seats=standard_seats(),
            created_at_ms=0,
            updated_at_ms=0,
        )
        encoded = room.canonical_json()
        self.assertIn('\"roomId\":\"room-branded\"', encoded)
        parsed = deserialize_room_state(encoded)
        self.assertIs(type(parsed.room_id), RoomId)
        self.assertTrue(all(type(seat.seat_id) is SeatId for seat in parsed.seats))
        self.assertEqual(
            RoomState.model_json_schema()["properties"]["roomId"]["type"],
            "string",
        )


class DomainInvariantTests(unittest.TestCase):
    def _empty_hands(self) -> tuple[PlayerHand, ...]:
        return tuple(
            PlayerHand(seat_id=SeatId(f"seat-{index}")) for index in range(4)
        )

    def test_representative_tile_meld_payment_and_action_invariants(self) -> None:
        with self.assertRaises(ValidationError):
            TileFace(family=TileFamily.BAMBOO, value=10)
        with self.assertRaises(ValidationError):
            MeldState(kind=MeldKind.PONG, tiles=(tile("a"), tile("b")))
        with self.assertRaises(ValidationError):
            Payment(
                sequence=1,
                payer_seat_id=SeatId("seat-0"),
                recipient_seat_id=SeatId("seat-0"),
                amount=1,
                reason="invalid self-payment",
            )
        with self.assertRaises(ValidationError):
            Chow(
                seat_id=SeatId("seat-0"),
                window_id=WindowId("window-1"),
                discard_sequence=1,
                tile_ids=(TileId("same"), TileId("same")),
            )
        with self.assertRaises(ValidationError):
            ClaimWindowRequested(
                window_id=WindowId("window-1"),
                discard_sequence=1,
                eligible_seat_ids=(SeatId("seat-1"), SeatId("seat-1")),
            )

    def test_unclaimed_discard_cannot_also_be_held(self) -> None:
        duplicate = tile("duplicate-discard")
        hands = list(self._empty_hands())
        hands[0] = PlayerHand(
            seat_id=SeatId("seat-0"), concealed_tiles=(duplicate,)
        )
        with self.assertRaises(ValidationError):
            HandState(
                hand_id=HandId("hand-duplicate"),
                player_hands=tuple(hands),
                discards=(
                    DiscardState(
                        sequence=1,
                        tile=duplicate,
                        discarded_by_seat_id=SeatId("seat-1"),
                    ),
                ),
            )

    def test_meld_claimed_discard_must_be_in_the_claimants_meld(self) -> None:
        claimed = tile("claimed-discard")
        hands = list(self._empty_hands())
        hands[1] = PlayerHand(
            seat_id=SeatId("seat-1"),
            melds=(
                MeldState(
                    kind=MeldKind.PONG,
                    tiles=(claimed, tile("pong-2"), tile("pong-3")),
                    claimed_from_seat_id=SeatId("seat-0"),
                    discard_sequence=1,
                ),
            ),
        )
        valid = HandState(
            hand_id=HandId("hand-claim"),
            player_hands=tuple(hands),
            discards=(
                DiscardState(
                    sequence=1,
                    tile=claimed,
                    discarded_by_seat_id=SeatId("seat-0"),
                    claimed_by_seat_id=SeatId("seat-1"),
                    claim_kind=ClaimKind.PONG,
                ),
            ),
        )
        self.assertEqual(valid.discards[0].tile.tile_id, TileId("claimed-discard"))

        with self.assertRaises(ValidationError):
            HandState(
                hand_id=HandId("hand-bad-claim"),
                player_hands=self._empty_hands(),
                discards=valid.discards,
            )

    def test_wall_discard_overlap_is_rejected(self) -> None:
        duplicate = tile("wall-and-discard")
        with self.assertRaises(ValidationError):
            HandState(
                hand_id=HandId("hand-wall-discard"),
                wall=WallState(live_tiles=(duplicate,)),
                player_hands=self._empty_hands(),
                discards=(
                    DiscardState(
                        sequence=1,
                        tile=duplicate,
                        discarded_by_seat_id=SeatId("seat-0"),
                    ),
                ),
            )

    def test_win_claimed_discard_cannot_remain_held(self) -> None:
        winning_discard = tile("winning-discard")
        hands = list(self._empty_hands())
        hands[1] = PlayerHand(
            seat_id=SeatId("seat-1"), concealed_tiles=(winning_discard,)
        )
        with self.assertRaises(ValidationError):
            HandState(
                hand_id=HandId("hand-win-duplicate"),
                player_hands=tuple(hands),
                discards=(
                    DiscardState(
                        sequence=1,
                        tile=winning_discard,
                        discarded_by_seat_id=SeatId("seat-0"),
                        claimed_by_seat_id=SeatId("seat-1"),
                        claim_kind=ClaimKind.WIN,
                    ),
                ),
            )

    def test_discard_seat_references_and_own_claim_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DiscardState(
                sequence=1,
                tile=tile("own-discard"),
                discarded_by_seat_id=SeatId("seat-0"),
                claimed_by_seat_id=SeatId("seat-0"),
                claim_kind=ClaimKind.WIN,
            )
        invalid_discards = (
            DiscardState(
                sequence=1,
                tile=tile("unknown-discarder"),
                discarded_by_seat_id=SeatId("unknown-seat"),
            ),
            DiscardState(
                sequence=1,
                tile=tile("unknown-claimant"),
                discarded_by_seat_id=SeatId("seat-0"),
                claimed_by_seat_id=SeatId("unknown-seat"),
                claim_kind=ClaimKind.WIN,
            ),
        )
        for discard in invalid_discards:
            with self.subTest(tile=discard.tile.tile_id), self.assertRaises(
                ValidationError
            ):
                HandState(
                    hand_id=HandId("hand-bad-seat-ref"),
                    player_hands=self._empty_hands(),
                    discards=(discard,),
                )

    def test_pending_claim_cardinality_eligibility_and_current_discard(self) -> None:
        bad_cardinalities = (
            (ClaimKind.CHOW, (TileId("a"),)),
            (ClaimKind.PONG, (TileId("a"),)),
            (ClaimKind.KONG, (TileId("a"), TileId("b"))),
            (ClaimKind.WIN, (TileId("a"),)),
            (ClaimKind.PASS, (TileId("a"),)),
        )
        for kind, tile_ids in bad_cardinalities:
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                PendingClaim(
                    window_id=WindowId("window-1"),
                    seat_id=SeatId("seat-1"),
                    kind=kind,
                    tile_ids=tile_ids,
                )

        ledger = (
            DiscardState(
                sequence=1,
                tile=tile("discard-1"),
                discarded_by_seat_id=SeatId("seat-0"),
            ),
        )
        with self.assertRaises(ValidationError):
            HandState(
                hand_id=HandId("hand-ineligible-claim"),
                phase=DiscardClaimsPhase(
                    window_id=WindowId("window-1"),
                    discard_sequence=1,
                    eligible_seat_ids=(SeatId("seat-1"),),
                ),
                player_hands=self._empty_hands(),
                discards=ledger,
                pending_claims=(
                    PendingClaim(
                        window_id=WindowId("window-1"),
                        seat_id=SeatId("seat-2"),
                        kind=ClaimKind.PASS,
                    ),
                ),
            )

        two_discards = (
            *ledger,
            DiscardState(
                sequence=2,
                tile=tile("discard-2"),
                discarded_by_seat_id=SeatId("seat-1"),
            ),
        )
        with self.assertRaises(ValidationError):
            HandState(
                hand_id=HandId("hand-stale-window"),
                phase=DiscardClaimsPhase(
                    window_id=WindowId("window-1"),
                    discard_sequence=1,
                    eligible_seat_ids=(SeatId("seat-2"),),
                ),
                player_hands=self._empty_hands(),
                discards=two_discards,
            )

    def test_claimed_meld_provenance_must_match_in_both_directions(self) -> None:
        claimed = tile("provenance-discard")
        cases = (
            (ClaimKind.CHOW, SeatId("seat-1"), SeatId("seat-0"), 1),
            (ClaimKind.PONG, SeatId("seat-2"), SeatId("seat-0"), 1),
            (ClaimKind.PONG, SeatId("seat-1"), SeatId("seat-2"), 1),
            (ClaimKind.PONG, SeatId("seat-1"), SeatId("seat-0"), 2),
            (None, None, SeatId("seat-0"), 1),
        )
        for claim_kind, claimed_by, claimed_from, meld_sequence in cases:
            hands = list(self._empty_hands())
            hands[1] = PlayerHand(
                seat_id=SeatId("seat-1"),
                melds=(
                    MeldState(
                        kind=MeldKind.PONG,
                        tiles=(claimed, tile("provenance-2"), tile("provenance-3")),
                        claimed_from_seat_id=claimed_from,
                        discard_sequence=meld_sequence,
                    ),
                ),
            )
            discard = DiscardState(
                sequence=1,
                tile=claimed,
                discarded_by_seat_id=SeatId("seat-0"),
                claimed_by_seat_id=claimed_by,
                claim_kind=claim_kind,
            )
            with self.subTest(
                kind=claim_kind,
                claimed_by=claimed_by,
                claimed_from=claimed_from,
                sequence=meld_sequence,
            ), self.assertRaises(ValidationError):
                HandState(
                    hand_id=HandId("hand-bad-provenance"),
                    player_hands=tuple(hands),
                    discards=(discard,),
                )

        with self.assertRaises(ValidationError):
            MeldState(
                kind=MeldKind.KONG,
                tiles=tuple(tile(f"concealed-{index}") for index in range(4)),
                concealed=True,
                claimed_from_seat_id=SeatId("seat-0"),
                discard_sequence=1,
            )

    def test_result_references_and_self_draw_provider_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            HandResult(
                outcome=HandOutcome.WIN,
                winner_seat_id=SeatId("seat-0"),
                provider_seat_id=SeatId("seat-1"),
                win_source=WinSource.SELF_DRAW,
            )

        bad_results = (
            HandResult(
                outcome=HandOutcome.WIN,
                winner_seat_id=SeatId("unknown-seat"),
                win_source=WinSource.SELF_DRAW,
            ),
            HandResult(
                outcome=HandOutcome.WIN,
                winner_seat_id=SeatId("seat-0"),
                provider_seat_id=SeatId("unknown-seat"),
                win_source=WinSource.DISCARD,
            ),
            HandResult(
                outcome=HandOutcome.TIE,
                payments=(
                    Payment(
                        sequence=1,
                        payer_seat_id=SeatId("unknown-seat"),
                        recipient_seat_id=SeatId("seat-0"),
                        amount=1,
                        reason="unknown result payer",
                    ),
                ),
            ),
        )
        for result in bad_results:
            with self.subTest(result=result), self.assertRaises(ValidationError):
                HandState(
                    hand_id=HandId("hand-bad-result"),
                    phase=CompletePhase(),
                    player_hands=self._empty_hands(),
                    result=result,
                )

    def test_match_history_result_and_payment_references_are_checked(self) -> None:
        seat_ids = tuple(SeatId(f"seat-{index}") for index in range(4))
        current_hand = HandState(
            hand_id=HandId("hand-current"), player_hands=self._empty_hands()
        )
        balances = tuple(SeatBalance(seat_id=seat_id) for seat_id in seat_ids)
        histories = (
            (
                HandResult(
                    outcome=HandOutcome.WIN,
                    winner_seat_id=SeatId("unknown-seat"),
                    win_source=WinSource.SELF_DRAW,
                ),
            ),
            (
                HandResult(
                    outcome=HandOutcome.TIE,
                    payments=(
                        Payment(
                            sequence=1,
                            payer_seat_id=SeatId("seat-0"),
                            recipient_seat_id=SeatId("unknown-seat"),
                            amount=1,
                            reason="unknown historical recipient",
                        ),
                    ),
                ),
            ),
        )
        for history in histories:
            with self.subTest(history=history), self.assertRaises(ValidationError):
                MatchState(
                    match_id=MatchId("match-bad-history"),
                    dealer_seat_id=seat_ids[0],
                    current_hand=current_hand,
                    hand_history=history,
                    balances=balances,
                )


class TaggedUnionTests(unittest.TestCase):
    def test_controller_descriptors_round_trip(self) -> None:
        adapter = TypeAdapter(SeatController)
        controllers = (
            ExternalSeatController(player_id=PlayerId("player-1")),
            AutomatedSeatController(policy_id="randomBot"),
        )
        for value in controllers:
            parsed = adapter.validate_json(value.canonical_json(), strict=True)
            self.assertEqual(parsed, value)
            self.assertIs(type(parsed), type(value))

    def test_observation_projection_and_public_meld_unions_round_trip(self) -> None:
        variants = (
            (
                SeatObservation,
                (
                    OwnSeatObservation(seat_id=SeatId("seat-0"), slot=0),
                    OpponentSeatObservation(seat_id=SeatId("seat-1"), slot=1),
                ),
            ),
            (
                PublicSeatView,
                (
                    SelfSeatView(seat_id=SeatId("seat-0"), slot=0),
                    OpponentSeatView(seat_id=SeatId("seat-1"), slot=1),
                ),
            ),
            (
                PublicMeldView,
                (
                    PublicExposedMeldView(
                        kind=MeldKind.PONG,
                        tiles=(PublicTileView(face=tile("public").face),) * 3,
                    ),
                    PublicConcealedMeldView(kind=MeldKind.KONG, tile_count=4),
                ),
            ),
        )
        for tagged_union, values in variants:
            adapter = TypeAdapter(tagged_union)
            for value in values:
                with self.subTest(
                    union=str(tagged_union), variant=type(value).__name__
                ):
                    parsed = adapter.validate_json(
                        value.canonical_json(), strict=True
                    )
                    self.assertEqual(parsed, value)
                    self.assertIs(type(parsed), type(value))

    def test_every_phase_round_trips_by_discriminator(self) -> None:
        adapter = TypeAdapter(HandPhase)
        phases = (
            SetupPhase(),
            AwaitingDrawPhase(seat_id=SeatId("seat-0")),
            AwaitingDiscardPhase(seat_id=SeatId("seat-0")),
            DiscardClaimsPhase(
                window_id=WindowId("window-1"),
                discard_sequence=1,
                eligible_seat_ids=(SeatId("seat-1"),),
            ),
            KongReplacementPhase(seat_id=SeatId("seat-0")),
            KongRobberyPhase(
                window_id=WindowId("window-2"),
                declaring_seat_id=SeatId("seat-0"),
                eligible_seat_ids=(SeatId("seat-1"),),
            ),
            CompletePhase(),
        )
        for phase in phases:
            with self.subTest(phase=phase.type):
                parsed = adapter.validate_json(phase.canonical_json(), strict=True)
                self.assertEqual(parsed, phase)
                self.assertIs(type(parsed), type(phase))

    def test_every_action_round_trips_by_discriminator(self) -> None:
        actions = (
            Draw(seat_id=SeatId("seat-0")),
            Discard(seat_id=SeatId("seat-0"), tile_id=TileId("tile-1")),
            Chow(
                seat_id=SeatId("seat-1"),
                window_id=WindowId("window-1"),
                discard_sequence=1,
                tile_ids=(TileId("tile-2"), TileId("tile-3")),
            ),
            Pong(
                seat_id=SeatId("seat-1"),
                window_id=WindowId("window-1"),
                discard_sequence=1,
                tile_ids=(TileId("tile-2"), TileId("tile-3")),
            ),
            Kong(
                seat_id=SeatId("seat-1"),
                kind=KongKind.CLAIMED,
                tile_ids=(TileId("tile-2"), TileId("tile-3"), TileId("tile-4")),
                window_id=WindowId("window-1"),
                discard_sequence=1,
            ),
            Pass(seat_id=SeatId("seat-1"), window_id=WindowId("window-1")),
            DeclareWin(seat_id=SeatId("seat-1"), window_id=WindowId("window-1")),
            Continue(seat_id=SeatId("seat-1")),
        )
        for action in actions:
            with self.subTest(action=action.type):
                parsed = parse_domain_action_json(action.canonical_json())
                self.assertEqual(parsed, action)
                self.assertIs(type(parsed), type(action))

    def test_every_event_round_trips_by_discriminator(self) -> None:
        physical_tile = tile()
        meld = MeldState(
            kind=MeldKind.PONG,
            tiles=(physical_tile, tile("tile-2"), tile("tile-3")),
        )
        result = HandResult(outcome=HandOutcome.TIE)
        events: tuple[DomainEvent, ...] = (
            HandSetupCompleted(hand_id=HandId("hand-1")),
            TileDrawn(seat_id=SeatId("seat-0"), tile=physical_tile),
            TileDiscarded(
                seat_id=SeatId("seat-0"), tile=physical_tile, discard_sequence=1
            ),
            ClaimSubmitted(
                window_id=WindowId("window-1"),
                seat_id=SeatId("seat-1"),
                kind=ClaimKind.PONG,
            ),
            MeldDeclared(seat_id=SeatId("seat-1"), meld=meld),
            KongDeclared(
                seat_id=SeatId("seat-1"),
                tile_ids=(TileId("tile-1"), TileId("tile-2")),
            ),
            WinDeclared(seat_id=SeatId("seat-1")),
            HandCompleted(result=result),
        )
        for event in events:
            with self.subTest(event=event.type):
                parsed = parse_domain_event_json(event.canonical_json())
                self.assertEqual(parsed, event)
                self.assertIs(type(parsed), type(event))

    def test_every_effect_round_trips_by_discriminator(self) -> None:
        effects: tuple[DomainEffect, ...] = (
            ClaimWindowRequested(
                window_id=WindowId("window-1"),
                discard_sequence=1,
                eligible_seat_ids=(SeatId("seat-1"), SeatId("seat-2")),
            ),
            AutomatedDecisionRequested(seat_id=SeatId("seat-2")),
        )
        for effect in effects:
            with self.subTest(effect=effect.type):
                parsed = parse_domain_effect_json(effect.canonical_json())
                self.assertEqual(parsed, effect)
                self.assertIs(type(parsed), type(effect))


class SnapshotAndEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.room = RoomState(
            room_id=RoomId("room-1"),
            seats=standard_seats(),
            created_at_ms=100,
            updated_at_ms=100,
        )

    def test_canonical_camel_case_json_round_trip(self) -> None:
        encoded = self.room.canonical_json()
        self.assertEqual(encoded, self.room.canonical_json())
        self.assertIn('"roomId":"room-1"', encoded)
        self.assertIn('"stateSchemaVersion":1', encoded)
        self.assertNotIn("room_id", encoded)
        self.assertEqual(deserialize_room_state(encoded), self.room)
        self.assertEqual(deserialize_room_state(encoded).canonical_json(), encoded)
        self.assertEqual(list(json.loads(encoded)), sorted(json.loads(encoded)))

    def test_rejects_wrong_ruleset_or_schema_version(self) -> None:
        data = json.loads(self.room.canonical_json())
        for key, bad_value in (
            ("rulesetId", "other"),
            ("rulesetVersion", "9.9.9"),
            ("stateSchemaVersion", 2),
        ):
            changed = {**data, key: bad_value}
            with self.subTest(key=key), self.assertRaises(ValidationError):
                deserialize_room_state(json.dumps(changed))

    def test_non_playable_engine_has_no_actions_and_typed_rejection(self) -> None:
        self.assertEqual(legal_actions(self.room, SeatId("seat-0")), ())
        action = Draw(seat_id=SeatId("seat-0"))
        with self.assertRaises(GameplayUnavailableError) as raised:
            transition(self.room, action)
        self.assertEqual(raised.exception.code, "GAMEPLAY_UNAVAILABLE")
        self.assertEqual(raised.exception.action_type, "draw")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
