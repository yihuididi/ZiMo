"""Public room-service contracts shared by orchestration layers."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import Field

if __package__.startswith("app."):
    from ..game import GameModel, PublicRoomView
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import GameModel, PublicRoomView


SOCKET_TICKET_TTL_MS = 30_000
DISCONNECT_GRACE_MS = 300_000


class RoomServiceError(RuntimeError):
    """Base for every expected, client-safe room-service rejection."""

    def __init__(
        self,
        code: str,
        status_code: int,
        message: str,
        *,
        current_revision: int | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.message = message
        self.current_revision = current_revision
        super().__init__(message)


class RoomCreation(GameModel):
    room_id: str
    player_id: str
    player_token: str = Field(repr=False)
    invite_token: str = Field(repr=False)
    view: PublicRoomView


class PlayerSession(GameModel):
    room_id: str
    player_id: str
    player_token: str = Field(repr=False)
    view: PublicRoomView


class CommandViewResult(GameModel):
    type: Literal["view"] = "view"
    view: PublicRoomView
    invite_token: str | None = Field(default=None, repr=False)

    def canonical_data(self) -> dict[str, Any]:
        value = super().canonical_data()
        if self.invite_token is None:
            value.pop("inviteToken", None)
        return value


class SessionEndedResult(GameModel):
    type: Literal["sessionEnded"] = "sessionEnded"
    revision: int = Field(ge=0)


CommandResult: TypeAlias = CommandViewResult | SessionEndedResult


class IssuedSocketTicket(GameModel):
    ticket: str = Field(repr=False)
    expires_at_ms: int = Field(ge=0)


class AuthenticatedPlayer(GameModel):
    player_id: str
    auth_generation: int = Field(ge=0)


class ProjectedRoomEvent(GameModel):
    public_sequence: int = Field(gt=0)
    revision: int = Field(ge=0)
    type: str
    payload: dict[str, str | int | bool | None]
    created_at_ms: int = Field(ge=0)


class ProjectedEvents(GameModel):
    events: tuple[ProjectedRoomEvent, ...]
    next_sequence: int = Field(ge=0)


__all__ = [
    "AuthenticatedPlayer",
    "CommandResult",
    "CommandViewResult",
    "DISCONNECT_GRACE_MS",
    "IssuedSocketTicket",
    "PlayerSession",
    "ProjectedEvents",
    "ProjectedRoomEvent",
    "RoomCreation",
    "RoomServiceError",
    "SOCKET_TICKET_TTL_MS",
    "SessionEndedResult",
]
