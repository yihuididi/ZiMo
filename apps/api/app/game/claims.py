"""Pure claim catalogues and arrival-order-independent resolution."""

from __future__ import annotations

from collections import defaultdict

from .actions import Chow, DomainAction, Kong, KongKind, Pass, Pong
from .model import (
    ClaimKind,
    DiscardClaimsPhase,
    HandState,
    PendingClaim,
    PlayerHand,
    SeatId,
    TileFamily,
)
from .tiles import sort_playable_tiles

CLAIM_PRIORITY = {
    ClaimKind.WIN: 3,
    ClaimKind.KONG: 2,
    ClaimKind.PONG: 2,
    ClaimKind.CHOW: 1,
}


def winning_claim(
    claims: tuple[PendingClaim, ...], seats: tuple[SeatId, ...], discarder: SeatId
) -> PendingClaim | None:
    candidates = [claim for claim in claims if claim.kind is not ClaimKind.PASS]
    return min(
        candidates,
        key=lambda c: (
            -CLAIM_PRIORITY[c.kind],
            (seats.index(c.seat_id) - seats.index(discarder)) % 4,
        ),
        default=None,
    )


def concealed_kongs(player: PlayerHand) -> tuple[Kong, ...]:
    groups = defaultdict(list)
    for tile in sort_playable_tiles(
        (*player.concealed_tiles, *((player.drawn_tile,) if player.drawn_tile else ()))
    ):
        groups[tile.face].append(tile)
    return tuple(
        Kong(
            seat_id=player.seat_id,
            kind=KongKind.CONCEALED,
            tile_ids=tuple(t.tile_id for t in tiles),
        )
        for tiles in groups.values()
        if len(tiles) == 4
    )


def claim_actions(
    hand: HandState, seat_id: SeatId, seats: tuple[SeatId, ...]
) -> tuple[DomainAction, ...]:
    phase = hand.phase
    if not isinstance(phase, DiscardClaimsPhase):
        return ()
    discard = hand.discards[-1]
    if seat_id == discard.discarded_by_seat_id:
        return ()
    player = next(p for p in hand.player_hands if p.seat_id == seat_id)
    face = discard.tile.face
    groups = defaultdict(list)
    for tile in sort_playable_tiles(player.concealed_tiles):
        groups[tile.face].append(tile)
    matching = groups[face]
    common = dict(
        seat_id=seat_id, window_id=phase.window_id, discard_sequence=discard.sequence
    )
    actions: list[DomainAction] = []
    if len(matching) == 3:
        actions.append(
            Kong(
                **common,
                kind=KongKind.CLAIMED,
                tile_ids=tuple(t.tile_id for t in matching),
            )
        )
    if face != player.last_discard_face:
        if len(matching) >= 2 and face not in player.passed_pong_faces:
            actions.append(
                Pong(**common, tile_ids=tuple(t.tile_id for t in matching[:2]))
            )
        if seats[
            (seats.index(discard.discarded_by_seat_id) + 1) % 4
        ] == seat_id and face.family in {
            TileFamily.BAMBOO,
            TileFamily.DOTS,
            TileFamily.CHARACTERS,
        }:
            rank = int(face.value)
            for start in range(max(1, rank - 2), min(7, rank) + 1):
                others = [
                    face.model_copy(update={"value": value})
                    for value in range(start, start + 3)
                    if value != rank
                ]
                if all(groups[value] for value in others):
                    actions.append(
                        Chow(
                            **common,
                            tile_ids=tuple(
                                groups[value][0].tile_id for value in others
                            ),
                        )
                    )
    if actions:
        actions.append(Pass(seat_id=seat_id, window_id=phase.window_id))
    return tuple(actions)
