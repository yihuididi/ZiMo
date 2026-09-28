"""Metadata and validation for the Singapore ruleset."""

from __future__ import annotations

from typing import ClassVar, Literal

from ..base import GameModel
from ..capabilities import ROOM_CAPABILITIES, RoomCapability
from ..config import GameConfig
from ..model import RoomState
from ..runtime import RandomSource
from ..singapore_game import SingaporeGameEngine, validate_room


class UnsupportedConfigurationError(ValueError):
    """Raised when a configuration is not supported."""


class SingaporeRules(GameModel):
    RULESET_ID: ClassVar[str] = "singapore"
    SEAT_COUNT: ClassVar[int] = 4
    TILE_COUNT: ClassVar[int] = 148
    RESERVE_TILE_COUNT: ClassVar[int] = 15
    CLAIM_WINDOW_MS: ClassVar[int] = 3000

    ruleset_id: Literal["singapore"] = "singapore"
    seat_count: Literal[4] = 4
    tile_count: Literal[148] = 148
    reserve_tile_count: Literal[15] = 15
    claim_window_ms: Literal[3000] = 3000

    @property
    def capabilities(self) -> tuple[RoomCapability, ...]:
        return ROOM_CAPABILITIES

    @property
    def configurable_fields(self) -> tuple[()]:
        return ()

    def default_config(self) -> GameConfig:
        return GameConfig()

    def normalize_config(self, value: GameConfig | dict[str, object]) -> GameConfig:
        normalized = GameConfig.normalized(value)
        if normalized != GameConfig():
            raise UnsupportedConfigurationError(
                "this ruleset does not advertise configurable game settings"
            )
        return normalized

    def validate_snapshot(self, room: RoomState) -> None:
        if room.ruleset_id != self.ruleset_id:
            raise ValueError("room snapshot ruleset is incompatible with SingaporeRules")
        if room.config != GameConfig():
            raise UnsupportedConfigurationError(
                "ruleset snapshot contains unsupported configuration"
            )
        validate_room(room, require_deadline=True)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def create_engine(self, rng: RandomSource | None = None) -> SingaporeGameEngine:
        return SingaporeGameEngine(rng)


__all__ = ["SingaporeRules", "UnsupportedConfigurationError"]
