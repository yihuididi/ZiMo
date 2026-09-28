"""Public capabilities of the Singapore game."""

from __future__ import annotations

from typing import Literal, TypeAlias

RoomCapability: TypeAlias = Literal[
    "multiplayerLobby", "roomEvents", "hibernatingWebSockets",
    "drawDiscard", "bonusTiles", "discardWindow", "chow", "pong",
    "kong3", "kong4",
]

ROOM_CAPABILITIES: tuple[RoomCapability, ...] = (
    "multiplayerLobby", "roomEvents", "hibernatingWebSockets",
    "drawDiscard", "bonusTiles", "discardWindow", "chow", "pong",
    "kong3", "kong4",
)

__all__ = ["RoomCapability", "ROOM_CAPABILITIES"]
