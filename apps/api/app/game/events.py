"""Immutable facts emitted by game transitions."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from .base import GameModel
from .model import (
    ClaimKind,
    HandId,
    HandResult,
    MeldState,
    PhysicalTile,
    SeatId,
    TileId,
    WindowId,
)


class HandSetupCompleted(GameModel):
    type: Literal["handSetupCompleted"] = "handSetupCompleted"
    hand_id: HandId = Field(min_length=1)


class TileDrawn(GameModel):
    type: Literal["tileDrawn"] = "tileDrawn"
    seat_id: SeatId = Field(min_length=1)
    tile: PhysicalTile
    replacement: bool = False


class TileDiscarded(GameModel):
    type: Literal["tileDiscarded"] = "tileDiscarded"
    seat_id: SeatId = Field(min_length=1)
    tile: PhysicalTile
    discard_sequence: int = Field(ge=1)


class ClaimSubmitted(GameModel):
    type: Literal["claimSubmitted"] = "claimSubmitted"
    window_id: WindowId = Field(min_length=1)
    seat_id: SeatId = Field(min_length=1)
    kind: ClaimKind


class MeldDeclared(GameModel):
    type: Literal["meldDeclared"] = "meldDeclared"
    seat_id: SeatId = Field(min_length=1)
    meld: MeldState


class KongDeclared(GameModel):
    type: Literal["kongDeclared"] = "kongDeclared"
    seat_id: SeatId = Field(min_length=1)
    tile_ids: tuple[TileId, ...]


class WinDeclared(GameModel):
    type: Literal["winDeclared"] = "winDeclared"
    seat_id: SeatId = Field(min_length=1)
    window_id: WindowId | None = None


class HandCompleted(GameModel):
    type: Literal["handCompleted"] = "handCompleted"
    result: HandResult


DomainEvent = Annotated[
    HandSetupCompleted
    | TileDrawn
    | TileDiscarded
    | ClaimSubmitted
    | MeldDeclared
    | KongDeclared
    | WinDeclared
    | HandCompleted,
    Field(discriminator="type"),
]

DOMAIN_EVENT_ADAPTER: TypeAdapter[DomainEvent] = TypeAdapter(DomainEvent)


def parse_domain_event_json(value: str | bytes) -> DomainEvent:
    return DOMAIN_EVENT_ADAPTER.validate_json(value, strict=True)
