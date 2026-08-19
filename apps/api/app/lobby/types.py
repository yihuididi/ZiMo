"""Transport-neutral lobby types shared by pure lobby transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

if "." in (__package__ or ""):
    from ..game import (
        GameModel,
        OpaqueActionDescriptor,
        PlayerId,
        PolicyId,
        RoomState,
        SeatId,
    )
else:  # pragma: no cover - Pyodide Worker module loading
    from game import (
        GameModel,
        OpaqueActionDescriptor,
        PlayerId,
        PolicyId,
        RoomState,
        SeatId,
    )


RANDOM_BOT_POLICY_ID = PolicyId("randomBot")
MAX_DISPLAY_NAME_LENGTH = 64


class LobbyDomainError(ValueError):
    """Expected pure-domain rejection with a stable transport-neutral code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class LobbyActionKind(StrEnum):
    READY = "ready"
    UNREADY = "unready"
    ADD_BOT = "addBot"
    FILL_BOTS = "fillBots"
    REMOVE_BOT = "removeBot"
    REMOVE_PLAYER = "removePlayer"
    LEAVE = "leave"
    ROTATE_INVITE = "rotateInvite"
    START_MATCH = "startMatch"
    START_AGAINST_BOTS = "startAgainstBots"


class LobbyAction(GameModel):
    kind: LobbyActionKind
    target_seat_id: SeatId | None = None
    target_player_id: PlayerId | None = None


@dataclass(frozen=True, slots=True)
class CataloguedLobbyAction:
    descriptor: OpaqueActionDescriptor
    action: LobbyAction


@dataclass(frozen=True, slots=True)
class LobbyTransition:
    state: RoomState
    event_type: str
    event_details: dict[str, object]
    additional_events: tuple[tuple[str, dict[str, object]], ...] = ()
    rotate_invite: bool = False
    session_ended: bool = False


__all__ = [
    "CataloguedLobbyAction",
    "LobbyAction",
    "LobbyActionKind",
    "LobbyDomainError",
    "LobbyTransition",
    "MAX_DISPLAY_NAME_LENGTH",
    "RANDOM_BOT_POLICY_ID",
]
