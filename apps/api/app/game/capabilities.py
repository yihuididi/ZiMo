"""Ruleset-versioned public capability metadata."""

from __future__ import annotations

from typing import Literal, TypeAlias


MILESTONE_2_RULESET_VERSION = "0.1.0"
MILESTONE_3_RULESET_VERSION = "0.2.0"
MILESTONE_3_STATE_SCHEMA_VERSION = 3

RoomCapability: TypeAlias = Literal[
    "multiplayerLobby",
    "roomEvents",
    "hibernatingWebSockets",
    "drawDiscard",
    "bonusTiles",
    "discardWindow",
]

MILESTONE_2_CAPABILITIES: tuple[RoomCapability, ...] = (
    "multiplayerLobby",
    "roomEvents",
    "hibernatingWebSockets",
)
MILESTONE_3_CAPABILITIES: tuple[RoomCapability, ...] = (
    *MILESTONE_2_CAPABILITIES,
    "drawDiscard",
    "bonusTiles",
    "discardWindow",
)


def capabilities_for_ruleset_version(
    ruleset_version: str,
) -> tuple[RoomCapability, ...]:
    if ruleset_version == MILESTONE_2_RULESET_VERSION:
        return MILESTONE_2_CAPABILITIES
    if ruleset_version == MILESTONE_3_RULESET_VERSION:
        return MILESTONE_3_CAPABILITIES
    raise ValueError(f"unsupported Singapore ruleset version: {ruleset_version}")


__all__ = [
    "MILESTONE_2_CAPABILITIES",
    "MILESTONE_2_RULESET_VERSION",
    "MILESTONE_3_CAPABILITIES",
    "MILESTONE_3_RULESET_VERSION",
    "MILESTONE_3_STATE_SCHEMA_VERSION",
    "RoomCapability",
    "capabilities_for_ruleset_version",
]
