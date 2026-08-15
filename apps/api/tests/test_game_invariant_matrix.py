from __future__ import annotations

from collections.abc import Callable, Iterable
import unittest

from pydantic import ValidationError

from app.game import (
    AutomatedSeatController,
    AwaitingDrawPhase,
    ClaimKind,
    CompletePhase,
    DiscardClaimsPhase,
    DiscardState,
    ExternalSeatController,
    GameConfig,
    HandId,
    HandOutcome,
    HandResult,
    HandState,
    Kong,
    KongKind,
    MatchId,
    MatchResult,
    MatchState,
    MatchStatus,
    MeldKind,
    MeldState,
    Pass,
    Payment,
    PendingClaim,
    PhysicalTile,
    PlayerHand,
    PlayerId,
    PlayerRole,
    PlayerState,
    PolicyId,
    Pong,
    RoomId,
    RoomState,
    RoomStatus,
    SeatBalance,
    SeatId,
    SeatState,
    SetupPhase,
    TileFace,
    TileFamily,
    TileId,
    WallState,
    WinSource,
    WindowId,
    standard_seats,
)


SEAT_IDS = tuple(SeatId(f"seat-{index}") for index in range(4))


def tile(tile_id: str, rank: int = 1) -> PhysicalTile:
    return PhysicalTile(
        tile_id=TileId(tile_id),
        face=TileFace(family=TileFamily.CHARACTERS, value=rank),
    )


def empty_hands(
    seat_ids: tuple[SeatId, ...] = SEAT_IDS,
) -> tuple[PlayerHand, ...]:
    return tuple(PlayerHand(seat_id=seat_id) for seat_id in seat_ids)


def hand_for(
    seat_ids: tuple[SeatId, ...] = SEAT_IDS,
    **changes: object,
) -> HandState:
    values: dict[str, object] = {
        "hand_id": HandId("hand-matrix"),
        "player_hands": empty_hands(seat_ids),
    }
    values.update(changes)
    return HandState(**values)


def balances_for(
    seat_ids: tuple[SeatId, ...] = SEAT_IDS,
) -> tuple[SeatBalance, ...]:
    return tuple(SeatBalance(seat_id=seat_id) for seat_id in seat_ids)


def active_match(
    seat_ids: tuple[SeatId, ...] = SEAT_IDS,
    **changes: object,
) -> MatchState:
    values: dict[str, object] = {
        "match_id": MatchId("match-matrix"),
        "dealer_seat_id": seat_ids[0],
        "current_hand": hand_for(seat_ids),
        "balances": balances_for(seat_ids),
    }
    values.update(changes)
    return MatchState(**values)


def finished_match(
    seat_ids: tuple[SeatId, ...] = SEAT_IDS,
    **changes: object,
) -> MatchState:
    final_balances = balances_for(seat_ids)
    values: dict[str, object] = {
        "match_id": MatchId("match-finished"),
        "status": MatchStatus.FINISHED,
        "dealer_seat_id": seat_ids[0],
        "balances": final_balances,
        "result": MatchResult(
            final_balances=final_balances,
            completed_at_ms=10,
        ),
    }
    values.update(changes)
    return MatchState(**values)


def automated_seats(
    seat_ids: tuple[SeatId, ...] = SEAT_IDS,
) -> tuple[SeatState, ...]:
    return tuple(
        SeatState(
            seat_id=seat_id,
            slot=index,
            controller=AutomatedSeatController(
                policy_id=PolicyId(f"policy-{index}")
            ),
            occupant_name=f"Bot {index}",
        )
        for index, seat_id in enumerate(seat_ids)
    )


def room_with(**changes: object) -> RoomState:
    values: dict[str, object] = {
        "room_id": RoomId("room-matrix"),
        "seats": standard_seats(),
        "created_at_ms": 1,
        "updated_at_ms": 1,
    }
    values.update(changes)
    return RoomState(**values)


class InvariantMatrixTestCase(unittest.TestCase):
    def assert_invalid(
        self,
        cases: Iterable[tuple[str, Callable[[], object]]],
    ) -> None:
        for name, factory in cases:
            with self.subTest(case=name), self.assertRaises(ValidationError):
                factory()


class LeafInvariantMatrixTests(InvariantMatrixTestCase):
    def test_identity_face_seat_hand_and_wall_branches(self) -> None:
        duplicate = tile("duplicate")
        with self.assertRaises(ValueError):
            RoomId("")
        with self.assertRaises(ValueError):
            RoomId("x" * 257)
        self.assert_invalid(
            (
                (
                    "suited non-integer",
                    lambda: TileFace(family=TileFamily.DOTS, value="one"),
                ),
                (
                    "empty honour name",
                    lambda: TileFace(family=TileFamily.DRAGON, value=""),
                ),
                (
                    "empty seat with occupant",
                    lambda: SeatState(
                        seat_id=SeatId("seat-empty"),
                        slot=0,
                        occupant_name="Ghost",
                    ),
                ),
                (
                    "duplicate held tile",
                    lambda: PlayerHand(
                        seat_id=SEAT_IDS[0],
                        concealed_tiles=(duplicate,),
                        drawn_tile=duplicate,
                    ),
                ),
                (
                    "duplicate initial ID",
                    lambda: PlayerHand(
                        seat_id=SEAT_IDS[0],
                        initial_tile_ids=(TileId("initial"), TileId("initial")),
                    ),
                ),
                (
                    "duplicate wall tile",
                    lambda: WallState(
                        live_tiles=(duplicate,), reserve_tiles=(duplicate,)
                    ),
                ),
            )
        )

    def test_meld_discard_pending_and_payment_branches(self) -> None:
        meld_tiles = (tile("meld-1"), tile("meld-2"), tile("meld-3"))
        self.assert_invalid(
            (
                (
                    "duplicate meld tile",
                    lambda: MeldState(
                        kind=MeldKind.PONG,
                        tiles=(meld_tiles[0], meld_tiles[0], meld_tiles[2]),
                    ),
                ),
                (
                    "claim source without sequence",
                    lambda: MeldState(
                        kind=MeldKind.PONG,
                        tiles=meld_tiles,
                        claimed_from_seat_id=SEAT_IDS[0],
                    ),
                ),
                (
                    "sequence without claim source",
                    lambda: MeldState(
                        kind=MeldKind.PONG,
                        tiles=meld_tiles,
                        discard_sequence=1,
                    ),
                ),
                (
                    "claimant without kind",
                    lambda: DiscardState(
                        sequence=1,
                        tile=tile("discard-a"),
                        discarded_by_seat_id=SEAT_IDS[0],
                        claimed_by_seat_id=SEAT_IDS[1],
                    ),
                ),
                (
                    "kind without claimant",
                    lambda: DiscardState(
                        sequence=1,
                        tile=tile("discard-b"),
                        discarded_by_seat_id=SEAT_IDS[0],
                        claim_kind=ClaimKind.PONG,
                    ),
                ),
                (
                    "PASS recorded as discard claim",
                    lambda: DiscardState(
                        sequence=1,
                        tile=tile("discard-pass"),
                        discarded_by_seat_id=SEAT_IDS[0],
                        claimed_by_seat_id=SEAT_IDS[1],
                        claim_kind=ClaimKind.PASS,
                    ),
                ),
                (
                    "duplicate pending tile ID",
                    lambda: PendingClaim(
                        window_id=WindowId("window-1"),
                        seat_id=SEAT_IDS[1],
                        kind=ClaimKind.PONG,
                        tile_ids=(TileId("same"), TileId("same")),
                    ),
                ),
                (
                    "self payment",
                    lambda: Payment(
                        sequence=1,
                        payer_seat_id=SEAT_IDS[0],
                        recipient_seat_id=SEAT_IDS[0],
                        amount=1,
                        reason="self",
                    ),
                ),
            )
        )

    def test_pong_and_every_kong_validation_branch(self) -> None:
        self.assert_invalid(
            (
                (
                    "Pong duplicate",
                    lambda: Pong(
                        seat_id=SEAT_IDS[0],
                        window_id=WindowId("window-1"),
                        discard_sequence=1,
                        tile_ids=(TileId("same"), TileId("same")),
                    ),
                ),
                (
                    "KONG_1 wrong cardinality",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.ADDED,
                        tile_ids=(TileId("a"), TileId("b")),
                    ),
                ),
                (
                    "KONG_3 wrong cardinality",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.CLAIMED,
                        tile_ids=(TileId("a"), TileId("b")),
                        window_id=WindowId("window-1"),
                        discard_sequence=1,
                    ),
                ),
                (
                    "KONG_4 wrong cardinality",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.CONCEALED,
                        tile_ids=(TileId("a"), TileId("b"), TileId("c")),
                    ),
                ),
                (
                    "Kong duplicate physical ID",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.CONCEALED,
                        tile_ids=(
                            TileId("a"),
                            TileId("a"),
                            TileId("c"),
                            TileId("d"),
                        ),
                    ),
                ),
                (
                    "KONG_3 missing window",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.CLAIMED,
                        tile_ids=(TileId("a"), TileId("b"), TileId("c")),
                        discard_sequence=1,
                    ),
                ),
                (
                    "KONG_3 missing sequence",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.CLAIMED,
                        tile_ids=(TileId("a"), TileId("b"), TileId("c")),
                        window_id=WindowId("window-1"),
                    ),
                ),
                (
                    "KONG_1 with window",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.ADDED,
                        tile_ids=(TileId("a"),),
                        window_id=WindowId("window-1"),
                    ),
                ),
                (
                    "KONG_4 with sequence",
                    lambda: Kong(
                        seat_id=SEAT_IDS[0],
                        kind=KongKind.CONCEALED,
                        tile_ids=(
                            TileId("a"),
                            TileId("b"),
                            TileId("c"),
                            TileId("d"),
                        ),
                        discard_sequence=1,
                    ),
                ),
            )
        )

    def test_hand_result_outcome_branches(self) -> None:
        self.assert_invalid(
            (
                (
                    "win without winner",
                    lambda: HandResult(
                        outcome=HandOutcome.WIN,
                        win_source=WinSource.SELF_DRAW,
                    ),
                ),
                (
                    "win without source",
                    lambda: HandResult(
                        outcome=HandOutcome.WIN,
                        winner_seat_id=SEAT_IDS[0],
                    ),
                ),
                (
                    "discard win without provider",
                    lambda: HandResult(
                        outcome=HandOutcome.WIN,
                        winner_seat_id=SEAT_IDS[0],
                        win_source=WinSource.DISCARD,
                    ),
                ),
                (
                    "winner is provider",
                    lambda: HandResult(
                        outcome=HandOutcome.WIN,
                        winner_seat_id=SEAT_IDS[0],
                        provider_seat_id=SEAT_IDS[0],
                        win_source=WinSource.DISCARD,
                    ),
                ),
                (
                    "non-win with winner",
                    lambda: HandResult(
                        outcome=HandOutcome.TIE,
                        winner_seat_id=SEAT_IDS[0],
                    ),
                ),
                (
                    "non-win with source",
                    lambda: HandResult(
                        outcome=HandOutcome.ABORTED,
                        win_source=WinSource.SELF_DRAW,
                    ),
                ),
            )
        )


class HandInvariantMatrixTests(InvariantMatrixTestCase):
    def test_shape_sequence_phase_and_pending_branches(self) -> None:
        ledger = (
            DiscardState(
                sequence=1,
                tile=tile("phase-discard"),
                discarded_by_seat_id=SEAT_IDS[0],
            ),
        )
        window = DiscardClaimsPhase(
            window_id=WindowId("window-1"),
            discard_sequence=1,
            eligible_seat_ids=(SEAT_IDS[1], SEAT_IDS[2]),
        )
        pass_one = PendingClaim(
            window_id=WindowId("window-1"),
            seat_id=SEAT_IDS[1],
            kind=ClaimKind.PASS,
        )
        self.assert_invalid(
            (
                (
                    "three hands",
                    lambda: hand_for(player_hands=empty_hands()[:3]),
                ),
                (
                    "duplicate hand seat",
                    lambda: hand_for(
                        player_hands=(
                            PlayerHand(seat_id=SEAT_IDS[0]),
                            PlayerHand(seat_id=SEAT_IDS[0]),
                            PlayerHand(seat_id=SEAT_IDS[2]),
                            PlayerHand(seat_id=SEAT_IDS[3]),
                        )
                    ),
                ),
                (
                    "non-contiguous discards",
                    lambda: hand_for(
                        discards=(
                            DiscardState(
                                sequence=2,
                                tile=tile("discard-seq-2"),
                                discarded_by_seat_id=SEAT_IDS[0],
                            ),
                        )
                    ),
                ),
                (
                    "non-contiguous payments",
                    lambda: hand_for(
                        payments=(
                            Payment(
                                sequence=2,
                                payer_seat_id=SEAT_IDS[0],
                                recipient_seat_id=SEAT_IDS[1],
                                amount=1,
                                reason="sequence",
                            ),
                        )
                    ),
                ),
                (
                    "duplicate payment sequences",
                    lambda: hand_for(
                        payments=(
                            Payment(
                                sequence=1,
                                payer_seat_id=SEAT_IDS[0],
                                recipient_seat_id=SEAT_IDS[1],
                                amount=1,
                                reason="first",
                            ),
                            Payment(
                                sequence=1,
                                payer_seat_id=SEAT_IDS[1],
                                recipient_seat_id=SEAT_IDS[2],
                                amount=1,
                                reason="duplicate",
                            ),
                        )
                    ),
                ),
                (
                    "complete phase without result",
                    lambda: hand_for(phase=CompletePhase()),
                ),
                (
                    "result without complete phase",
                    lambda: hand_for(result=HandResult(outcome=HandOutcome.TIE)),
                ),
                (
                    "phase unknown seat",
                    lambda: hand_for(
                        phase=AwaitingDrawPhase(seat_id=SeatId("unknown"))
                    ),
                ),
                (
                    "phase duplicate seats",
                    lambda: hand_for(
                        phase=DiscardClaimsPhase(
                            window_id=WindowId("window-1"),
                            discard_sequence=1,
                            eligible_seat_ids=(SEAT_IDS[1], SEAT_IDS[1]),
                        ),
                        discards=ledger,
                    ),
                ),
                (
                    "pending unknown seat",
                    lambda: hand_for(
                        phase=window,
                        discards=ledger,
                        pending_claims=(
                            PendingClaim(
                                window_id=WindowId("window-1"),
                                seat_id=SeatId("unknown"),
                                kind=ClaimKind.PASS,
                            ),
                        ),
                    ),
                ),
                (
                    "duplicate pending seat/window",
                    lambda: hand_for(
                        phase=window,
                        discards=ledger,
                        pending_claims=(pass_one, pass_one),
                    ),
                ),
                (
                    "pending wrong window",
                    lambda: hand_for(
                        phase=window,
                        discards=ledger,
                        pending_claims=(
                            pass_one.model_copy(
                                update={"window_id": WindowId("window-other")}
                            ),
                        ),
                    ),
                ),
            )
        )

    def test_payment_tile_conservation_and_result_reference_branches(self) -> None:
        duplicate = tile("held-twice")
        hands = list(empty_hands())
        hands[0] = PlayerHand(
            seat_id=SEAT_IDS[0], concealed_tiles=(duplicate,)
        )
        hands[1] = PlayerHand(
            seat_id=SEAT_IDS[1], concealed_tiles=(duplicate,)
        )
        duplicate_discard = DiscardState(
            sequence=1,
            tile=tile("ledger-duplicate"),
            discarded_by_seat_id=SEAT_IDS[0],
        )
        self.assert_invalid(
            (
                (
                    "payment unknown seat",
                    lambda: hand_for(
                        payments=(
                            Payment(
                                sequence=1,
                                payer_seat_id=SeatId("unknown"),
                                recipient_seat_id=SEAT_IDS[1],
                                amount=1,
                                reason="unknown",
                            ),
                        )
                    ),
                ),
                (
                    "wall and held overlap",
                    lambda: hand_for(
                        wall=WallState(live_tiles=(duplicate,)),
                        player_hands=tuple(hands),
                    ),
                ),
                (
                    "held by two seats",
                    lambda: hand_for(player_hands=tuple(hands)),
                ),
                (
                    "duplicate discard physical ID",
                    lambda: hand_for(
                        discards=(
                            duplicate_discard,
                            duplicate_discard.model_copy(update={"sequence": 2}),
                        )
                    ),
                ),
                (
                    "result unknown winner",
                    lambda: hand_for(
                        phase=CompletePhase(),
                        result=HandResult(
                            outcome=HandOutcome.WIN,
                            winner_seat_id=SeatId("unknown"),
                            win_source=WinSource.SELF_DRAW,
                        ),
                    ),
                ),
                (
                    "result payment unknown seat",
                    lambda: hand_for(
                        phase=CompletePhase(),
                        result=HandResult(
                            outcome=HandOutcome.TIE,
                            payments=(
                                Payment(
                                    sequence=1,
                                    payer_seat_id=SEAT_IDS[0],
                                    recipient_seat_id=SeatId("unknown"),
                                    amount=1,
                                    reason="unknown",
                                ),
                            ),
                        ),
                    ),
                ),
            )
        )


class MatchInvariantMatrixTests(InvariantMatrixTestCase):
    def test_match_result_branches(self) -> None:
        balances = balances_for()
        duplicate_balances = (
            balances[0],
            balances[0],
            balances[2],
            balances[3],
        )
        self.assert_invalid(
            (
                (
                    "three result balances",
                    lambda: MatchResult(
                        final_balances=balances[:3], completed_at_ms=1
                    ),
                ),
                (
                    "duplicate result balance",
                    lambda: MatchResult(
                        final_balances=duplicate_balances, completed_at_ms=1
                    ),
                ),
                (
                    "duplicate winners",
                    lambda: MatchResult(
                        final_balances=balances,
                        winning_seat_ids=(SEAT_IDS[0], SEAT_IDS[0]),
                        completed_at_ms=1,
                    ),
                ),
                (
                    "unknown winner",
                    lambda: MatchResult(
                        final_balances=balances,
                        winning_seat_ids=(SeatId("unknown"),),
                        completed_at_ms=1,
                    ),
                ),
            )
        )

    def test_match_balance_dealer_hand_and_status_branches(self) -> None:
        balances = balances_for()
        final_result = MatchResult(final_balances=balances, completed_at_ms=1)
        other_seats = tuple(SeatId(f"other-{index}") for index in range(4))
        self.assert_invalid(
            (
                (
                    "three balances",
                    lambda: MatchState(
                        match_id=MatchId("match"),
                        dealer_seat_id=SEAT_IDS[0],
                        current_hand=hand_for(),
                        balances=balances[:3],
                    ),
                ),
                (
                    "duplicate balances",
                    lambda: MatchState(
                        match_id=MatchId("match"),
                        dealer_seat_id=SEAT_IDS[0],
                        current_hand=hand_for(),
                        balances=(balances[0], balances[0], balances[2], balances[3]),
                    ),
                ),
                (
                    "unknown dealer",
                    lambda: active_match(dealer_seat_id=SeatId("unknown")),
                ),
                (
                    "current hand seat mismatch",
                    lambda: active_match(current_hand=hand_for(other_seats)),
                ),
                (
                    "active without hand",
                    lambda: active_match(current_hand=None),
                ),
                (
                    "active with result",
                    lambda: active_match(result=final_result),
                ),
                (
                    "finished with current hand",
                    lambda: finished_match(current_hand=hand_for()),
                ),
                (
                    "finished without result",
                    lambda: finished_match(result=None),
                ),
                (
                    "finished result seat mismatch",
                    lambda: finished_match(
                        result=MatchResult(
                            final_balances=balances_for(other_seats),
                            completed_at_ms=1,
                        )
                    ),
                ),
            )
        )

    def test_match_history_result_and_payment_branches(self) -> None:
        self.assert_invalid(
            (
                (
                    "history unknown provider",
                    lambda: active_match(
                        hand_history=(
                            HandResult(
                                outcome=HandOutcome.WIN,
                                winner_seat_id=SEAT_IDS[0],
                                provider_seat_id=SeatId("unknown"),
                                win_source=WinSource.DISCARD,
                            ),
                        )
                    ),
                ),
                (
                    "history unknown payment seat",
                    lambda: active_match(
                        hand_history=(
                            HandResult(
                                outcome=HandOutcome.TIE,
                                payments=(
                                    Payment(
                                        sequence=1,
                                        payer_seat_id=SeatId("unknown"),
                                        recipient_seat_id=SEAT_IDS[0],
                                        amount=1,
                                        reason="unknown",
                                    ),
                                ),
                            ),
                        )
                    ),
                ),
            )
        )


class RoomInvariantMatrixTests(InvariantMatrixTestCase):
    def test_room_seat_player_host_and_controller_branches(self) -> None:
        seats = standard_seats()
        player = PlayerState(
            player_id=PlayerId("player-1"),
            display_name="One",
            role=PlayerRole.HOST,
            joined_at_ms=1,
        )
        member = PlayerState(
            player_id=PlayerId("player-2"),
            display_name="Two",
            role=PlayerRole.MEMBER,
            joined_at_ms=1,
        )
        controlled = seats[0].model_copy(
            update={
                "controller": ExternalSeatController(player_id=player.player_id),
                "occupant_name": "One",
            }
        )
        self.assert_invalid(
            (
                ("three room seats", lambda: room_with(seats=seats[:3])),
                (
                    "invalid slots",
                    lambda: room_with(
                        seats=(
                            seats[0],
                            seats[1].model_copy(update={"slot": 0}),
                            seats[2],
                            seats[3],
                        )
                    ),
                ),
                (
                    "duplicate seat IDs",
                    lambda: room_with(
                        seats=(
                            seats[0],
                            seats[1].model_copy(update={"seat_id": seats[0].seat_id}),
                            seats[2],
                            seats[3],
                        )
                    ),
                ),
                (
                    "duplicate player IDs",
                    lambda: room_with(
                        seats=(controlled, *seats[1:]),
                        players=(player, player.model_copy(update={"display_name": "Copy"})),
                    ),
                ),
                (
                    "no host",
                    lambda: room_with(
                        seats=(
                            seats[0].model_copy(
                                update={
                                    "controller": ExternalSeatController(
                                        player_id=member.player_id
                                    )
                                }
                            ),
                            *seats[1:],
                        ),
                        players=(member,),
                    ),
                ),
                (
                    "two hosts",
                    lambda: room_with(
                        seats=(
                            controlled,
                            seats[1].model_copy(
                                update={
                                    "controller": ExternalSeatController(
                                        player_id=member.player_id
                                    )
                                }
                            ),
                            *seats[2:],
                        ),
                        players=(
                            player,
                            member.model_copy(update={"role": PlayerRole.HOST}),
                        ),
                    ),
                ),
                (
                    "player controls two seats",
                    lambda: room_with(
                        seats=(
                            controlled,
                            seats[1].model_copy(
                                update={
                                    "controller": ExternalSeatController(
                                        player_id=player.player_id
                                    )
                                }
                            ),
                            *seats[2:],
                        ),
                        players=(player,),
                    ),
                ),
                (
                    "controller references unknown player",
                    lambda: room_with(
                        seats=(
                            seats[0].model_copy(
                                update={
                                    "controller": ExternalSeatController(
                                        player_id=PlayerId("unknown")
                                    )
                                }
                            ),
                            *seats[1:],
                        ),
                        players=(player,),
                    ),
                ),
            )
        )

    def test_room_ready_match_status_and_timestamp_branches(self) -> None:
        occupied = automated_seats()
        active = active_match()
        inactive = finished_match()
        not_ready = PlayerState(
            player_id=PlayerId("human"),
            display_name="Human",
            role=PlayerRole.HOST,
            ready=False,
            joined_at_ms=1,
        )
        human_seat = occupied[0].model_copy(
            update={
                "controller": ExternalSeatController(player_id=not_ready.player_id),
                "occupant_name": "Human",
            }
        )
        other_seat_ids = tuple(SeatId(f"other-{index}") for index in range(4))
        self.assert_invalid(
            (
                (
                    "READY with empty seat",
                    lambda: room_with(
                        status=RoomStatus.READY,
                        seats=(standard_seats()[0], *occupied[1:]),
                    ),
                ),
                (
                    "READY with unready human",
                    lambda: room_with(
                        status=RoomStatus.READY,
                        seats=(human_seat, *occupied[1:]),
                        players=(not_ready,),
                    ),
                ),
                (
                    "IN_MATCH without match",
                    lambda: room_with(status=RoomStatus.IN_MATCH, seats=occupied),
                ),
                (
                    "IN_MATCH with finished match",
                    lambda: room_with(
                        status=RoomStatus.IN_MATCH,
                        seats=occupied,
                        match=inactive,
                    ),
                ),
                (
                    "IN_MATCH with empty seat",
                    lambda: room_with(
                        status=RoomStatus.IN_MATCH,
                        seats=(standard_seats()[0], *occupied[1:]),
                        match=active,
                    ),
                ),
                (
                    "FINISHED with active match",
                    lambda: room_with(
                        status=RoomStatus.FINISHED,
                        seats=occupied,
                        match=active,
                    ),
                ),
                (
                    "pre-match room carrying match",
                    lambda: room_with(
                        status=RoomStatus.WAITING_FOR_PLAYERS,
                        seats=occupied,
                        match=active,
                    ),
                ),
                (
                    "match seat mismatch",
                    lambda: room_with(
                        status=RoomStatus.IN_MATCH,
                        seats=occupied,
                        match=active_match(other_seat_ids),
                    ),
                ),
                (
                    "updated before created",
                    lambda: room_with(created_at_ms=2, updated_at_ms=1),
                ),
            )
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
