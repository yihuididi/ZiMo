"""Allow-listed public tile, meld, and discard representations."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .base import GameModel
from .model import (
    ClaimKind,
    DiscardState,
    MeldKind,
    MeldState,
    PhysicalTile,
    SeatId,
    TileFace,
)


class PublicTileView(GameModel):
    """A logical tile face with no physical tile identity."""

    face: TileFace


class PublicExposedMeldView(GameModel):
    visibility: Literal["exposed"] = "exposed"
    kind: MeldKind
    tiles: tuple[PublicTileView, ...]
    claimed_from_seat_id: SeatId | None = None
    discard_sequence: int | None = Field(default=None, ge=1)


class PublicConcealedMeldView(GameModel):
    """A concealed meld exposes its public kind/count, never tile faces or IDs."""

    visibility: Literal["concealed"] = "concealed"
    kind: MeldKind
    tile_count: int = Field(gt=0)


PublicMeldView = Annotated[
    PublicExposedMeldView | PublicConcealedMeldView,
    Field(discriminator="visibility"),
]


class PublicDiscardView(GameModel):
    sequence: int = Field(ge=1)
    tile: PublicTileView
    discarded_by_seat_id: SeatId
    claimed_by_seat_id: SeatId | None = None
    claim_kind: ClaimKind | None = None


def project_public_tile(tile: PhysicalTile) -> PublicTileView:
    return PublicTileView(face=tile.face)


def project_public_meld(meld: MeldState) -> PublicMeldView:
    if meld.concealed:
        return PublicConcealedMeldView(kind=meld.kind, tile_count=len(meld.tiles))
    return PublicExposedMeldView(
        kind=meld.kind,
        tiles=tuple(project_public_tile(tile) for tile in meld.tiles),
        claimed_from_seat_id=meld.claimed_from_seat_id,
        discard_sequence=meld.discard_sequence,
    )


def project_public_discard(discard: DiscardState) -> PublicDiscardView:
    return PublicDiscardView(
        sequence=discard.sequence,
        tile=project_public_tile(discard.tile),
        discarded_by_seat_id=discard.discarded_by_seat_id,
        claimed_by_seat_id=discard.claimed_by_seat_id,
        claim_kind=discard.claim_kind,
    )


# Short aliases for consumers that do not use the UI-oriented ``View`` suffix.
PublicTile = PublicTileView
PublicMeld = PublicMeldView
PublicDiscard = PublicDiscardView
