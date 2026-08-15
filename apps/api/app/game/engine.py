"""Pure engine ports and the intentionally non-playable Milestone 1 engine."""

from __future__ import annotations

from typing import Protocol

from .actions import DomainAction
from .base import GameModel
from .effects import DomainEffect
from .events import DomainEvent
from .model import PlayerId, RoomState, SeatId
from .observation import PlayerObservation
from .projection import OpaqueActionDescriptor, PublicRoomView


MILESTONE_1_CAPABILITIES: tuple[()] = ()


class GameplayUnavailableError(RuntimeError):
    """Typed rejection used while the Milestone 1 engine is non-playable."""

    code = "GAMEPLAY_UNAVAILABLE"

    def __init__(self, action: DomainAction) -> None:
        self.action_type = action.type
        super().__init__(
            f"{self.code}: action {action.type!r} is not enabled by ruleset 0.1.0"
        )


class TransitionResult(GameModel):
    state: RoomState
    domain_events: tuple[DomainEvent, ...] = ()
    effects: tuple[DomainEffect, ...] = ()


class GameEngine(Protocol):
    capabilities: tuple[()]

    def transition(
        self, state: RoomState, action: DomainAction
    ) -> TransitionResult:
        """Apply one legal action without reading clocks or doing I/O."""

    def legal_actions(
        self, state: RoomState, seat_id: SeatId
    ) -> tuple[DomainAction, ...]:
        """Return fully specified domain actions for the given seat."""


class ObservationBuilder(Protocol):
    def __call__(
        self,
        room: RoomState,
        viewer_player_id: PlayerId,
        *,
        capabilities: tuple[()] = (),
    ) -> PlayerObservation: ...


class ProjectionBuilder(Protocol):
    def __call__(
        self,
        room: RoomState,
        viewer_player_id: PlayerId,
        *,
        server_time_ms: int,
        capabilities: tuple[()] = (),
        actions: tuple[OpaqueActionDescriptor, ...] = (),
        **kwargs: object,
    ) -> PublicRoomView: ...


class MilestoneOneEngine:
    """Advertises no gameplay and rejects every otherwise well-typed action."""

    capabilities = MILESTONE_1_CAPABILITIES

    def transition(
        self, state: RoomState, action: DomainAction
    ) -> TransitionResult:
        del state
        raise GameplayUnavailableError(action)

    def legal_actions(
        self, state: RoomState, seat_id: SeatId
    ) -> tuple[DomainAction, ...]:
        del state, seat_id
        return ()


_MILESTONE_ONE_ENGINE = MilestoneOneEngine()


def transition(state: RoomState, action: DomainAction) -> TransitionResult:
    return _MILESTONE_ONE_ENGINE.transition(state, action)


def legal_actions(state: RoomState, seat_id: SeatId) -> tuple[DomainAction, ...]:
    return _MILESTONE_ONE_ENGINE.legal_actions(state, seat_id)
