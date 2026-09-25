"""Versioned metadata and validation for the concrete Singapore ruleset."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import model_validator

from ..base import GameModel
from ..capabilities import (
    MILESTONE_2_RULESET_VERSION,
    MILESTONE_3_RULESET_VERSION,
    MILESTONE_3_STATE_SCHEMA_VERSION,
    RoomCapability,
    capabilities_for_ruleset_version,
)
from ..config import GameConfig
from ..engine import validate_milestone_three_room
from ..model import RoomState


class UnsupportedConfigurationError(ValueError):
    """Raised when a future configuration is requested before its capability."""


class SingaporeRules(GameModel):
    RULESET_ID: ClassVar[str] = "singapore"
    RULESET_VERSION: ClassVar[str] = MILESTONE_3_RULESET_VERSION
    STATE_SCHEMA_VERSION: ClassVar[int] = MILESTONE_3_STATE_SCHEMA_VERSION
    SEAT_COUNT: ClassVar[int] = 4
    TILE_COUNT: ClassVar[int] = 148
    RESERVE_TILE_COUNT: ClassVar[int] = 15
    CLAIM_WINDOW_MS: ClassVar[int] = 3000

    ruleset_id: Literal["singapore"] = "singapore"
    ruleset_version: Literal["0.1.0", "0.2.0"] = MILESTONE_3_RULESET_VERSION
    state_schema_version: Literal[2, 3] = MILESTONE_3_STATE_SCHEMA_VERSION
    seat_count: Literal[4] = 4
    tile_count: Literal[148] = 148
    reserve_tile_count: Literal[15] = 15
    claim_window_ms: Literal[3000] = 3000

    @model_validator(mode="after")
    def validate_version_schema(self) -> "SingaporeRules":
        if (
            self.ruleset_version == MILESTONE_3_RULESET_VERSION
            and self.state_schema_version != MILESTONE_3_STATE_SCHEMA_VERSION
        ):
            raise ValueError("draw/discard preview requires state schema version 3")
        return self

    @property
    def capabilities(self) -> tuple[RoomCapability, ...]:
        return capabilities_for_ruleset_version(self.ruleset_version)

    @property
    def configurable_fields(self) -> tuple[()]:
        return ()

    def default_config(self) -> GameConfig:
        return GameConfig()

    def normalize_config(
        self, value: GameConfig | dict[str, object]
    ) -> GameConfig:
        normalized = GameConfig.normalized(value)
        if normalized != GameConfig():
            raise UnsupportedConfigurationError(
                "this ruleset does not advertise configurable game settings"
            )
        return normalized

    def validate_snapshot(self, room: RoomState) -> None:
        if (
            room.ruleset_id != self.ruleset_id
            or room.ruleset_version != self.ruleset_version
        ):
            raise ValueError("room snapshot version is incompatible with SingaporeRules")
        if room.config != GameConfig():
            raise UnsupportedConfigurationError(
                "ruleset snapshot contains unsupported configuration"
            )
        if room.ruleset_version == MILESTONE_3_RULESET_VERSION:
            validate_milestone_three_room(room, require_deadline=True)
        elif room.pending_deadline is not None:
            raise ValueError("legacy ruleset cannot contain a gameplay deadline")

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


def rules_for_version(ruleset_version: str) -> SingaporeRules:
    if ruleset_version not in {
        MILESTONE_2_RULESET_VERSION,
        MILESTONE_3_RULESET_VERSION,
    }:
        raise ValueError(f"unsupported Singapore ruleset version: {ruleset_version}")
    return SingaporeRules(
        ruleset_version=ruleset_version,
        # Migration 4 rewrites legacy 0.1 snapshots into the canonical v3
        # envelope without changing their pinned, non-playable ruleset.
        state_schema_version=MILESTONE_3_STATE_SCHEMA_VERSION,
    )


__all__ = [
    "SingaporeRules",
    "UnsupportedConfigurationError",
    "rules_for_version",
]
