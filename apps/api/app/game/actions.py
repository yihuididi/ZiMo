"""Typed commands accepted by the pure game engine."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from .base import GameModel
from .model import SeatId, TileId, WindowId


class KongKind(StrEnum):
    CONCEALED = "KONG_4"
    ADDED = "KONG_1"
    CLAIMED = "KONG_3"


class Draw(GameModel):
    type: Literal["draw"] = "draw"
    seat_id: SeatId = Field(min_length=1)


class Discard(GameModel):
    type: Literal["discard"] = "discard"
    seat_id: SeatId = Field(min_length=1)
    tile_id: TileId = Field(min_length=1)


class Chow(GameModel):
    type: Literal["chow"] = "chow"
    seat_id: SeatId = Field(min_length=1)
    window_id: WindowId = Field(min_length=1)
    discard_sequence: int = Field(ge=1)
    tile_ids: tuple[TileId, TileId]

    @model_validator(mode="after")
    def validate_tiles(self) -> "Chow":
        if self.tile_ids[0] == self.tile_ids[1]:
            raise ValueError("Chow must consume two distinct physical tiles")
        return self


class Pong(GameModel):
    type: Literal["pong"] = "pong"
    seat_id: SeatId = Field(min_length=1)
    window_id: WindowId = Field(min_length=1)
    discard_sequence: int = Field(ge=1)
    tile_ids: tuple[TileId, TileId]

    @model_validator(mode="after")
    def validate_tiles(self) -> "Pong":
        if self.tile_ids[0] == self.tile_ids[1]:
            raise ValueError("Pong must consume two distinct physical tiles")
        return self


class Kong(GameModel):
    type: Literal["kong"] = "kong"
    seat_id: SeatId = Field(min_length=1)
    kind: KongKind
    tile_ids: tuple[TileId, ...]
    window_id: WindowId | None = None
    discard_sequence: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_kong(self) -> "Kong":
        required = {
            KongKind.ADDED: 1,
            KongKind.CLAIMED: 3,
            KongKind.CONCEALED: 4,
        }[self.kind]
        if len(self.tile_ids) != required:
            raise ValueError(f"{self.kind.value} must specify exactly {required} tiles")
        if len(self.tile_ids) != len(set(self.tile_ids)):
            raise ValueError("Kong cannot consume the same physical tile twice")
        is_claimed = self.kind is KongKind.CLAIMED
        if is_claimed != (self.window_id is not None):
            raise ValueError("only KONG_3 requires a claim window")
        if is_claimed != (self.discard_sequence is not None):
            raise ValueError("only KONG_3 requires a discard sequence")
        return self


class Pass(GameModel):
    type: Literal["pass"] = "pass"
    seat_id: SeatId = Field(min_length=1)
    window_id: WindowId = Field(min_length=1)


class DeclareWin(GameModel):
    type: Literal["declareWin"] = "declareWin"
    seat_id: SeatId = Field(min_length=1)
    window_id: WindowId | None = None


class Continue(GameModel):
    type: Literal["continue"] = "continue"
    seat_id: SeatId = Field(min_length=1)


DomainAction = Annotated[
    Draw | Discard | Chow | Pong | Kong | Pass | DeclareWin | Continue,
    Field(discriminator="type"),
]

DOMAIN_ACTION_ADAPTER: TypeAdapter[DomainAction] = TypeAdapter(DomainAction)


def parse_domain_action_json(value: str | bytes) -> DomainAction:
    """Parse strict tagged action JSON without losing its concrete type."""

    return DOMAIN_ACTION_ADAPTER.validate_json(value, strict=True)
