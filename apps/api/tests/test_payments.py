"""Milestone 6 payer vectors, immediate awards, and ledger invariants."""

from __future__ import annotations

import pytest

from app.game import GameConfig, MeldKind, MeldState, SeatId, TileFamily, WinSource, canonical_physical_deck, validate_room
from app.game.payments import award_immediate, settle_win
from test_game_claims import started
from test_game_setup import IdentityRandomSource


@pytest.mark.parametrize(
    ("shooter", "source", "pattern", "expected"),
    [
        (False, WinSource.DISCARD, "STANDARD", {"seat-0": 16, "seat-1": 8, "seat-3": 8}),
        (True, WinSource.DISCARD, "STANDARD", {"seat-0": 32}),
        (False, WinSource.SELF_DRAW, "STANDARD", {"seat-0": 16, "seat-1": 16, "seat-3": 16}),
        (False, WinSource.DISCARD, "THIRTEEN_WONDERS", {"seat-0": 16, "seat-1": 16, "seat-3": 16}),
        (True, WinSource.DISCARD, "THIRTEEN_WONDERS", {"seat-0": 48}),
        (True, WinSource.ROBBED_KONG, "STANDARD", {"seat-0": 32}),
        (False, WinSource.ROBBED_KONG, "THIRTEEN_WONDERS", {"seat-0": 16, "seat-1": 8, "seat-3": 8}),
    ],
)
def test_win_payer_vectors(shooter, source, pattern, expected):
    _, room = started(IdentityRandomSource())
    room = room.model_copy(update={"config": GameConfig(shooter_mode=shooter)})
    match = room.match
    hand = match.current_hand
    prior = len(hand.payments)
    match, hand, base = settle_win(
        room, match, hand, winner=SeatId("seat-2"),
        provider=None if source is WinSource.SELF_DRAW else SeatId("seat-0"),
        source=source, pattern=pattern, capped_fan=3,
    )
    assert base == 8
    assert {str(payment.payer_seat_id): payment.amount for payment in hand.payments[prior:]} == expected
    assert sum(balance.points for balance in match.balances) == 0
    assert match.balances[2].points == sum(expected.values())


def test_nonlinear_payout_and_negative_balances():
    _, room = started(IdentityRandomSource())
    room = room.model_copy(update={"config": GameConfig(payout_table=(1, 3, 6, 12, 24, 48))})
    match, hand, base = settle_win(
        room, room.match, room.match.current_hand,
        winner=SeatId("seat-2"), provider=SeatId("seat-0"),
        source=WinSource.DISCARD, pattern="STANDARD", capped_fan=4,
    )
    assert base == 24
    assert match.balances[0].points < 0
    assert match.balances[2].points > 0
    assert sum(balance.points for balance in match.balances) == 0


def test_flower_pair_provenance_and_one_time_award():
    _, room = started(IdentityRandomSource())
    match = room.match
    hand = match.current_hand
    number = 1
    bonus = [tile for tile in canonical_physical_deck(hand.hand_id) if tile.face.family in {TileFamily.FLOWER, TileFamily.SEASON} and tile.face.value == number]
    assert len(bonus) == 2
    player = hand.player_hands[0]
    player = player.model_copy(update={
        "bonus_tiles": tuple(bonus),
        "initial_tile_ids": (*player.initial_tile_ids[:-2], bonus[0].tile_id, bonus[1].tile_id),
    })
    hand = hand.model_copy(update={"player_hands": (player, *hand.player_hands[1:])})
    match, awarded = award_immediate(room, match, hand)
    amount = room.config.initial_thirteen_pair_payment
    pair = [payment for payment in awarded.payments if payment.reason == "Flower/season pair 1"]
    assert len(pair) == 3
    assert all(payment.amount == amount for payment in pair)
    again_match, again = award_immediate(room, match, awarded)
    assert again.payments == awarded.payments
    assert again_match.balances == match.balances


def test_forged_balance_fails_validation():
    _, room = started(IdentityRandomSource())
    balances = list(room.match.balances)
    balances[0] = balances[0].model_copy(update={"points": 1})
    forged = room.model_copy(update={
        "match": room.match.model_copy(update={"balances": tuple(balances)}),
    })
    with pytest.raises(ValueError, match="balances do not reconcile"):
        validate_room(forged)


def test_off_wind_pair_charges_only_matching_wind_holder():
    _, room = started(IdentityRandomSource())
    hand = room.match.current_hand
    bonus = [tile for tile in canonical_physical_deck(hand.hand_id) if tile.face.family in {TileFamily.FLOWER, TileFamily.SEASON} and tile.face.value == 1]
    player = hand.player_hands[1].model_copy(update={"bonus_tiles": tuple(bonus)})
    hand = hand.model_copy(update={"player_hands": (hand.player_hands[0], player, *hand.player_hands[2:])})
    _, awarded = award_immediate(room, room.match, hand)
    pair = [payment for payment in awarded.payments if payment.reason == "Flower/season pair 1"]
    assert len(pair) == 1
    assert pair[0].payer_seat_id == SeatId("seat-0")
    assert pair[0].recipient_seat_id == SeatId("seat-1")
    assert pair[0].amount == room.config.flower_season_pair_payment


def test_distinct_bonus_awards_stack_without_repeating():
    _, room = started(IdentityRandomSource())
    hand = room.match.current_hand
    bonus = [tile for tile in canonical_physical_deck(hand.hand_id)
             if tile.face.family is TileFamily.ANIMAL
             or (tile.face.family in {TileFamily.FLOWER, TileFamily.SEASON} and tile.face.value == 1)]
    player = hand.player_hands[0].model_copy(update={"bonus_tiles": tuple(bonus)})
    hand = hand.model_copy(update={"player_hands": (player, *hand.player_hands[1:])})
    match, awarded = award_immediate(room, room.match, hand)
    reasons = {payment.reason for payment in awarded.payments}
    assert reasons == {
        "Complete animal set", "Animal pair CAT/MOUSE",
        "Animal pair ROOSTER/CENTIPEDE", "Flower/season pair 1",
    }
    assert len(awarded.payments) == 12
    assert sum(balance.points for balance in match.balances) == 0
    assert award_immediate(room, match, awarded)[1].payments == awarded.payments


@pytest.mark.parametrize("shooter", [False, True])
def test_kong_three_payment_uses_discarder_in_shooter_mode(shooter):
    _, room = started(IdentityRandomSource())
    room = room.model_copy(update={"config": GameConfig(shooter_mode=shooter)})
    hand = room.match.current_hand
    tiles = [tile for tile in canonical_physical_deck(hand.hand_id) if tile.face.family is TileFamily.DRAGON and tile.face.value == "RED"]
    meld = MeldState(kind=MeldKind.KONG, kong_kind="KONG_3", tiles=tuple(tiles), claimed_from_seat_id=SeatId("seat-0"), discard_sequence=1)
    player = hand.player_hands[1].model_copy(update={"melds": (meld,)})
    hand = hand.model_copy(update={"player_hands": (hand.player_hands[0], player, *hand.player_hands[2:])})
    _, awarded = award_immediate(room, room.match, hand)
    kong = [payment for payment in awarded.payments if payment.reason.startswith("Kong-3")]
    assert len(kong) == (1 if shooter else 3)
    assert sum(payment.amount for payment in kong) == 3 * room.config.kong_three_payment
    if shooter:
        assert kong[0].payer_seat_id == SeatId("seat-0")
