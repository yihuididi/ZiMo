"""Immutable Singapore Mahjong configuration values."""

from __future__ import annotations

from pydantic import Field, model_validator

from .base import GameModel


class GameConfig(GameModel):
    """The complete normalized configuration shape reserved by the roadmap.

    Milestone 1 does not make these options editable or playable.  Defining the
    final shape now lets snapshots remain stable as capabilities are enabled by
    later ruleset versions.
    """

    shooter_mode: bool = False
    minimum_fan: int = Field(default=1, gt=0)
    maximum_fan: int = Field(default=5, gt=0)
    payout_table: tuple[int, ...] = (1, 2, 4, 8, 16, 32)

    kong_one_payment: int = Field(default=2, gt=0)
    kong_three_payment: int = Field(default=2, gt=0)
    complete_animal_set_payment: int = Field(default=4, gt=0)
    complete_flower_set_payment: int = Field(default=4, gt=0)
    complete_season_set_payment: int = Field(default=4, gt=0)
    animal_pair_payment: int = Field(default=2, gt=0)
    flower_season_pair_payment: int = Field(default=2, gt=0)
    initial_thirteen_pair_payment: int = Field(default=4, gt=0)

    fresh_discard_threshold: int = Field(default=4, gt=0)
    fresh_kong_threshold: int = Field(default=7, gt=0)

    seven_pairs_enabled: bool = False
    fresh_kong_pay_all_enabled: bool = False
    kong_four_robbery_enabled: bool = False
    concealed_self_draw_bonus_enabled: bool = False
    automatic_dragon_wins_enabled: bool = True
    automatic_wind_wins_enabled: bool = True
    extra_self_draw_points: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_payout_settings(self) -> "GameConfig":
        if self.minimum_fan > self.maximum_fan:
            raise ValueError("minimum_fan cannot exceed maximum_fan")
        if len(self.payout_table) != self.maximum_fan + 1:
            raise ValueError(
                "payout_table must contain one positive value for every fan "
                "from zero through maximum_fan"
            )
        if any(value <= 0 for value in self.payout_table):
            raise ValueError("payout_table values must be positive")
        if any(
            later < earlier
            for earlier, later in zip(self.payout_table, self.payout_table[1:])
        ):
            raise ValueError("payout_table values must be non-decreasing")
        if self.initial_thirteen_pair_payment < max(
            self.animal_pair_payment, self.flower_season_pair_payment
        ):
            raise ValueError(
                "initial_thirteen_pair_payment cannot be lower than a normal "
                "pair payment"
            )
        return self

    @classmethod
    def normalized(cls, value: "GameConfig | dict[str, object]") -> "GameConfig":
        """Validate and return the immutable normalized configuration."""

        if isinstance(value, cls):
            return value
        return cls.model_validate(value)
