"""Public-evidence Bao triggers and hand-local liability replacement."""

from __future__ import annotations

from .model import BaoLiability, ClaimKind, HandState, MeldKind, RoomState, SeatId, TileFamily, Wind
from .scoring import HONORS, WinEvaluation, _bonus_awards, _decompositions, _face


def fresh_discard(hand: HandState, sequence: int) -> bool:
    discard = hand.discards[sequence - 1]
    return not any(d.tile.face == discard.tile.face for d in hand.discards[:sequence - 1])


def qualifying_liability(
    room: RoomState, before: HandState, beneficiary: SeatId, kind: ClaimKind,
    evaluation: WinEvaluation | None = None,
) -> BaoLiability | None:
    """Evaluate only the accepted claim, against evidence before it resolved."""
    discard = before.discards[-1]
    player = next(p for p in before.player_hands if p.seat_id == beneficiary)
    face = discard.tile.face
    seats = tuple(s.seat_id for s in sorted(room.seats, key=lambda s: s.slot))
    own = tuple(Wind)[(seats.index(beneficiary) - seats.index(room.match.dealer_seat_id)) % 4]
    prevailing = room.match.prevailing_wind
    sets = {m.tiles[0].face for m in player.melds if m.kind in {MeldKind.PONG, MeldKind.KONG}}
    reasons = []
    completes_set = kind in {ClaimKind.PONG, ClaimKind.KONG}
    if kind is ClaimKind.WIN:
        faces = tuple(_face(t.face) for t in player.concealed_tiles) + (_face(face),)
        completes_set = any(
            any(k == "PONG" and values[0] == _face(face) for k, values in groups)
            for _, groups in _decompositions(faces, 4 - len(player.melds))
        ) or (evaluation is not None and evaluation.pattern in {"ALL_DRAGONS", "ALL_WINDS"}
              and sum(t.face == face for t in player.concealed_tiles) >= 2)
    if completes_set:
        for family, count, reason in ((TileFamily.DRAGON, 2, "DRAGONS"), (TileFamily.WIND, 3, "WINDS")):
            if face.family is family and face not in sets and sum(f.family is family for f in sets) == count:
                reasons.append(reason)

    def honor_fan(value):
        if value.family is TileFamily.DRAGON:
            return 1
        if value.family is TileFamily.WIND:
            return int(value.value == own.value) + int(value.value == prevailing.value)
        return 0

    def visible_honor_fan(exposed):
        dragons = {f for f in exposed if f.family is TileFamily.DRAGON}
        winds = {f for f in exposed if f.family is TileFamily.WIND}
        return ((7 if len(dragons) == 3 else len(dragons))
                + (12 if len(winds) == 4 else sum(honor_fan(f) for f in winds)))

    bonus_fan = sum(a.fan for a in _bonus_awards(player, own))
    visible = visible_honor_fan(sets) + bonus_fan
    after = visible_honor_fan(sets | {face}) + bonus_fan if completes_set else visible
    if kind in {ClaimKind.PONG, ClaimKind.KONG, ClaimKind.WIN} and honor_fan(face) and max(visible, after) >= room.config.maximum_fan:
        reasons.append("VISIBLE_FAN_LIMIT")
    if kind is ClaimKind.WIN:
        def color(family):
            return "HONORS" if family in HONORS else family.value

        if (evaluation is not None and any(a.name == "Full Color" for a in evaluation.awards)
                and len(player.melds) in {3, 4}
                and all(color(t.face.family) == color(face.family) for m in player.melds for t in m.tiles)):
            reasons.append("FULL_COLOR")
        if discard.live_tiles_remaining < room.config.fresh_discard_threshold and fresh_discard(before, discard.sequence):
            reasons.append("FRESH_DISCARD")
    if not reasons:
        return None
    return BaoLiability(
        beneficiary_seat_id=beneficiary, feeder_seat_id=discard.discarded_by_seat_id,
        reasons=tuple(reasons), discard_sequence=discard.sequence,
    )


def record_liability(hand: HandState, liability: BaoLiability | None) -> HandState:
    if liability is None:
        return hand
    values = {b.beneficiary_seat_id: b for b in hand.bao_liabilities}
    values[liability.beneficiary_seat_id] = liability
    return hand.model_copy(update={"bao_liabilities": tuple(values[key] for key in sorted(values))})
