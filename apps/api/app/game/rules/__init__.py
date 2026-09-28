"""Registry of supported game rulesets."""

from __future__ import annotations

from typing import Protocol

from ..config import GameConfig
from ..engine import GameEngine
from ..model import RoomState
from ..runtime import RandomSource

from .singapore import (
    SingaporeRules,
    UnsupportedConfigurationError,
)


class GameRules(Protocol):
    ruleset_id: str
    capabilities: tuple[str, ...]

    def default_config(self) -> GameConfig: ...
    def normalize_config(self, value: GameConfig | dict[str, object]) -> GameConfig: ...
    def validate_snapshot(self, room: RoomState) -> None: ...
    def create_engine(self, rng: RandomSource | None = None) -> GameEngine: ...


_RULESETS: dict[str, GameRules] = {"singapore": SingaporeRules()}


def rules_for_id(ruleset_id: str) -> GameRules:
    try:
        return _RULESETS[ruleset_id]
    except KeyError as exc:
        raise ValueError(f"unsupported ruleset: {ruleset_id}") from exc


__all__ = ["GameRules", "SingaporeRules", "UnsupportedConfigurationError", "rules_for_id"]
