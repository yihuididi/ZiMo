"""Metadata and configuration boundary for Singapore Mahjong ruleset 0.1.0."""

from __future__ import annotations

from typing import ClassVar, Literal

from ..base import GameModel
from ..config import GameConfig
from ..model import RoomState


class UnsupportedConfigurationError(ValueError):
    """Raised when a future configuration is requested before its capability."""


class SingaporeRules(GameModel):
    RULESET_ID: ClassVar[str] = "singapore"
    RULESET_VERSION: ClassVar[str] = "0.1.0"
    STATE_SCHEMA_VERSION: ClassVar[int] = 2
    SEAT_COUNT: ClassVar[int] = 4
    TILE_COUNT: ClassVar[int] = 148
    RESERVE_TILE_COUNT: ClassVar[int] = 15
    CLAIM_WINDOW_MS: ClassVar[int] = 3000

    ruleset_id: Literal["singapore"] = "singapore"
    ruleset_version: Literal["0.1.0"] = "0.1.0"
    state_schema_version: Literal[2] = 2
    seat_count: Literal[4] = 4
    tile_count: Literal[148] = 148
    reserve_tile_count: Literal[15] = 15
    claim_window_ms: Literal[3000] = 3000
    capabilities: tuple[()] = ()
    configurable_fields: tuple[()] = ()

    def default_config(self) -> GameConfig:
        return GameConfig()

    def normalize_config(
        self, value: GameConfig | dict[str, object]
    ) -> GameConfig:
        normalized = GameConfig.normalized(value)
        if normalized != GameConfig():
            raise UnsupportedConfigurationError(
                "ruleset 0.1.0 does not advertise configurable game settings"
            )
        return normalized

    def validate_snapshot(self, room: RoomState) -> None:
        if (
            room.ruleset_id != self.ruleset_id
            or room.ruleset_version != self.ruleset_version
            or room.state_schema_version != self.state_schema_version
        ):
            raise ValueError("room snapshot version is incompatible with SingaporeRules")
        if room.config != GameConfig():
            raise UnsupportedConfigurationError(
                "ruleset 0.1.0 snapshot contains unsupported configuration"
            )

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities
