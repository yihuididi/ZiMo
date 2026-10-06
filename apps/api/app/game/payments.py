"""Pure, deterministic single-hand Singapore payment calculations."""

from __future__ import annotations

from .bao import fresh_discard
from .model import (
    PayerAmount, Settlement, KongRobberyPhase,
    HandState, MatchState, MeldKind, Payment, RoomState, SeatBalance, SeatId,
    TileFamily, WinSource,
)


def _seats(room: RoomState) -> tuple[SeatId, ...]:
    return tuple(seat.seat_id for seat in sorted(room.seats, key=lambda seat: seat.slot))


def _wind_seat(room: RoomState, match: MatchState, number: int) -> SeatId:
    seats = _seats(room)
    dealer = match.dealer_seat_id
    return seats[(seats.index(dealer) + number - 1) % 4]


def _append(
    match: MatchState, hand: HandState,
    transfers: list[tuple[SeatId, SeatId, int, str]],
) -> tuple[MatchState, HandState]:
    if not transfers:
        return match, hand
    payments = list(hand.payments)
    balances = {entry.seat_id: entry.points for entry in match.balances}
    for payer, recipient, amount, reason in transfers:
        if amount <= 0 or payer == recipient:
            raise ValueError("invalid payment transfer")
        payments.append(Payment(
            sequence=len(payments) + 1, payer_seat_id=payer,
            recipient_seat_id=recipient, amount=amount, reason=reason,
        ))
        balances[payer] -= amount
        balances[recipient] += amount
    hand = hand.model_copy(update={"payments": tuple(payments)})
    match = match.model_copy(update={
        "balances": tuple(SeatBalance(seat_id=entry.seat_id, points=balances[entry.seat_id]) for entry in match.balances),
        "current_hand": hand,
    })
    return match, hand


def award_immediate(room: RoomState, match: MatchState, hand: HandState) -> tuple[MatchState, HandState]:
    """Award each physical Kong and bonus pattern once as soon as it exists."""
    config = room.config
    seats = _seats(room)
    prior = {(str(p.recipient_seat_id), p.reason) for p in hand.payments}
    transfers: list[tuple[SeatId, SeatId, int, str]] = []

    def award(recipient: SeatId, reason: str, amount: int, payers: tuple[SeatId, ...]) -> None:
        key = (str(recipient), reason)
        if key in prior:
            return
        prior.add(key)
        transfers.extend((payer, recipient, amount, reason) for payer in payers if payer != recipient)

    for player in hand.player_hands:
        seat = player.seat_id
        others = tuple(other for other in seats if other != seat)
        for meld in player.melds:
            if meld.kind is not MeldKind.KONG or meld.kong_kind not in {"KONG_1", "KONG_3"}:
                continue
            face = meld.tiles[0].face
            reason = f"Kong-{meld.kong_kind[-1]}: {str(face.value).title()} {face.family.value.title()}"
            if meld.kong_kind == "KONG_1":
                award(seat, reason, config.kong_one_payment, others)
            elif meld.claimed_from_seat_id is not None and (
                config.shooter_mode or (
                    config.fresh_kong_pay_all_enabled and meld.discard_sequence is not None
                    and hand.discards[meld.discard_sequence - 1].live_tiles_remaining < config.fresh_kong_threshold
                    and fresh_discard(hand, meld.discard_sequence)
                )
            ):
                award(seat, reason, 3 * config.kong_three_payment, (meld.claimed_from_seat_id,))
            else:
                award(seat, reason, config.kong_three_payment, others)

        bonus = {(tile.face.family, tile.face.value): tile for tile in player.bonus_tiles}
        if all((TileFamily.ANIMAL, value) in bonus for value in ("CAT", "MOUSE", "ROOSTER", "CENTIPEDE")):
            award(seat, "Complete animal set", config.complete_animal_set_payment, others)
        for family, amount, name in (
            (TileFamily.FLOWER, config.complete_flower_set_payment, "flower"),
            (TileFamily.SEASON, config.complete_season_set_payment, "season"),
        ):
            if all((family, number) in bonus for number in range(1, 5)):
                award(seat, f"Complete {name} set", amount, others)
        for a, b in (("CAT", "MOUSE"), ("ROOSTER", "CENTIPEDE")):
            if (TileFamily.ANIMAL, a) in bonus and (TileFamily.ANIMAL, b) in bonus:
                raw = set(player.initial_tile_ids)
                amount = (config.initial_thirteen_pair_payment
                          if all(bonus[(TileFamily.ANIMAL, value)].tile_id in raw for value in (a, b))
                          else config.animal_pair_payment)
                award(seat, f"Animal pair {a}/{b}", amount, others)
        for number in range(1, 5):
            flower = bonus.get((TileFamily.FLOWER, number))
            season = bonus.get((TileFamily.SEASON, number))
            if flower is None or season is None:
                continue
            raw = set(player.initial_tile_ids)
            amount = (
                config.initial_thirteen_pair_payment
                if flower.tile_id in raw and season.tile_id in raw
                else config.flower_season_pair_payment
            )
            wind_seat = _wind_seat(room, match, number)
            payers = others if wind_seat == seat else (wind_seat,)
            award(seat, f"Flower/season pair {number}", amount, payers)
    return _append(match, hand, transfers)


def settle_win(
    room: RoomState, match: MatchState, hand: HandState, *,
    winner: SeatId, provider: SeatId | None, source: WinSource,
    pattern: str, capped_fan: int,
) -> tuple[MatchState, HandState, int]:
    """Settle a legal win from the frozen room configuration."""
    config = room.config
    base = config.payout_table[capped_fan]
    others = tuple(seat for seat in _seats(room) if seat != winner)
    transfers: list[tuple[SeatId, SeatId, int, str]] = []
    robbery_kind = hand.phase.kong_kind if isinstance(hand.phase, KongRobberyPhase) else None
    wonders_vector = pattern == "THIRTEEN_WONDERS" and (source is WinSource.DISCARD or robbery_kind == "KONG_4")
    if source is WinSource.SELF_DRAW or (wonders_vector and not config.shooter_mode):
        reason = "13 Wonders discard" if source is not WinSource.SELF_DRAW else "Self-draw Game"
        transfers = [(seat, winner, 2 * base, reason) for seat in others]
    elif provider is None:
        raise ValueError("discard win requires a provider")
    elif wonders_vector:
        transfers = [(provider, winner, 6 * base, "13 Wonders shooter Game")]
    elif config.shooter_mode:
        transfers = [(provider, winner, 4 * base, "Shooter discard Game")]
    else:
        transfers = [
            (seat, winner, (2 if seat == provider else 1) * base,
             "Discard provider Game" if seat == provider else "Discard Game")
            for seat in others
        ]
    if source is WinSource.SELF_DRAW:
        transfers = [(payer, recipient, amount + config.extra_self_draw_points, reason)
                     for payer, recipient, amount, reason in transfers]
    baseline = tuple(PayerAmount(seat_id=payer, amount=amount) for payer, _, amount, _ in transfers)
    liability = next((b for b in hand.bao_liabilities if b.beneficiary_seat_id == winner), None)
    if liability is not None and source is not WinSource.SELF_DRAW and liability.feeder_seat_id != provider:
        liability = None
    if liability is not None:
        transfers = [(liability.feeder_seat_id, winner, sum(p.amount for p in baseline), "Bao pay-all Game")]
    settlement = Settlement(
        baseline=baseline, liability=liability,
        final=tuple(PayerAmount(seat_id=payer, amount=amount) for payer, _, amount, _ in transfers),
        robbed_kong_kind=robbery_kind,
    )
    hand = hand.model_copy(update={"settlement": settlement})
    match, hand = _append(match, hand, transfers)
    return match, hand, base


__all__ = ["award_immediate", "settle_win"]
