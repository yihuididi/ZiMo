"""Contracts shared by game engines and their callers."""

from __future__ import annotations

from typing import Protocol

from .actions import DomainAction
from .base import GameModel
from .capabilities import RoomCapability
from .effects import DomainEffect
from .events import DomainEvent
from .model import PlayerId, RoomState, SeatId, WindowId
from .observation import PlayerObservation
from .projection import OpaqueActionDescriptor, PublicRoomView


MAX_AUTOMATED_CONTINUATIONS = 32


class IllegalGameActionError(ValueError):
    """Generic legal-action rejection that discloses no hidden state."""

    code = "ACTION_NOT_AVAILABLE"

    def __init__(self) -> None:
        super().__init__("action is not available")


class InvalidGameStateError(ValueError):
    pass


class TransitionResult(GameModel):
    state: RoomState
    domain_events: tuple[DomainEvent, ...] = ()
    effects: tuple[DomainEffect, ...] = ()


class GameEngine(Protocol):
    capabilities: tuple[RoomCapability, ...]

    def setup_match(self, state: RoomState) -> TransitionResult: ...

    def transition(
        self, state: RoomState, action: DomainAction
    ) -> TransitionResult: ...

    def legal_actions(
        self, state: RoomState, seat_id: SeatId
    ) -> tuple[DomainAction, ...]: ...

    def resolve_discard_window(
        self, state: RoomState, window_id: WindowId
    ) -> TransitionResult: ...


class ObservationBuilder(Protocol):
    def __call__(
        self,
        room: RoomState,
        viewer_player_id: PlayerId,
        *,
        capabilities: tuple[RoomCapability, ...] | None = None,
    ) -> PlayerObservation: ...


class ProjectionBuilder(Protocol):
    def __call__(
        self,
        room: RoomState,
        viewer_player_id: PlayerId,
        *,
        server_time_ms: int,
        capabilities: tuple[RoomCapability, ...] | None = None,
        actions: tuple[OpaqueActionDescriptor, ...] = (),
        **kwargs: object,
    ) -> PublicRoomView: ...


def finalize_completed_preview(state: RoomState, *, completed_at_ms: int) -> RoomState:
    from .singapore_game import finalize_completed_preview as finalize

    return finalize(state, completed_at_ms=completed_at_ms)


def transition(state: RoomState, action: DomainAction) -> TransitionResult:
    from .singapore_game import SingaporeGameEngine

    return SingaporeGameEngine().transition(state, action)


def legal_actions(state: RoomState, seat_id: SeatId) -> tuple[DomainAction, ...]:
    from .singapore_game import SingaporeGameEngine

    return SingaporeGameEngine().legal_actions(state, seat_id)


__all__ = [
    "GameEngine", "IllegalGameActionError", "InvalidGameStateError",
    "MAX_AUTOMATED_CONTINUATIONS", "ObservationBuilder", "ProjectionBuilder",
    "TransitionResult", "finalize_completed_preview", "legal_actions", "transition",
]
