"""Requests for orchestration work emitted by pure game transitions."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from .base import GameModel
from .model import SeatId, WindowId


class ClaimWindowRequested(GameModel):
    type: Literal["claimWindowRequested"] = "claimWindowRequested"
    window_id: WindowId = Field(min_length=1)
    discard_sequence: int = Field(ge=1)
    eligible_seat_ids: tuple[SeatId, ...]
    duration_ms: int = Field(default=3000, gt=0)

    @model_validator(mode="after")
    def validate_seats(self) -> "ClaimWindowRequested":
        if len(self.eligible_seat_ids) != len(set(self.eligible_seat_ids)):
            raise ValueError("eligible claim seats must be unique")
        return self


class AutomatedDecisionRequested(GameModel):
    type: Literal["automatedDecisionRequested"] = "automatedDecisionRequested"
    seat_id: SeatId = Field(min_length=1)


DomainEffect = Annotated[
    ClaimWindowRequested | AutomatedDecisionRequested,
    Field(discriminator="type"),
]

DOMAIN_EFFECT_ADAPTER: TypeAdapter[DomainEffect] = TypeAdapter(DomainEffect)


def parse_domain_effect_json(value: str | bytes) -> DomainEffect:
    return DOMAIN_EFFECT_ADAPTER.validate_json(value, strict=True)
