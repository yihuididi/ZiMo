"""Controller-facing policy ports; external seats deliberately have no chooser."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol

from .actions import DomainAction
from .model import AutomatedSeatController, PolicyId, RoomState, SeatId
from .observation import PlayerObservation, build_seat_observation
from .runtime import RandomSource


class NoLegalActionsError(RuntimeError):
    pass


class UnknownAutomatedPolicyError(LookupError):
    pass


class AutomatedPolicy(Protocol):
    policy_id: PolicyId

    def choose_action(
        self,
        observation: PlayerObservation,
        legal_actions: tuple[DomainAction, ...],
        rng: RandomSource,
    ) -> DomainAction:
        """Choose synchronously using only the supplied observation and actions."""


class AutomatedPolicySelector(Protocol):
    def select(self, policy_id: PolicyId) -> AutomatedPolicy:
        """Resolve a persisted policy descriptor to an injected policy."""


class RandomBotPolicy:
    policy_id = PolicyId("randomBot")

    def choose_action(
        self,
        observation: PlayerObservation,
        legal_actions: tuple[DomainAction, ...],
        rng: RandomSource,
    ) -> DomainAction:
        del observation
        if not legal_actions:
            raise NoLegalActionsError("the automated seat has no legal actions")
        return legal_actions[rng.randbelow(len(legal_actions))]


class StaticAutomatedPolicySelector:
    def __init__(self, policies: Iterable[AutomatedPolicy] | None = None) -> None:
        configured = tuple(policies) if policies is not None else (RandomBotPolicy(),)
        self._policies: Mapping[PolicyId, AutomatedPolicy] = {
            policy.policy_id: policy for policy in configured
        }
        if len(self._policies) != len(configured):
            raise ValueError("automated policy IDs must be unique")

    def select(self, policy_id: PolicyId) -> AutomatedPolicy:
        try:
            return self._policies[policy_id]
        except KeyError as exc:
            raise UnknownAutomatedPolicyError(
                f"unsupported automated policy: {policy_id}"
            ) from exc


def choose_automated_action(
    room: RoomState,
    seat_id: SeatId,
    legal_actions: tuple[DomainAction, ...],
    rng: RandomSource,
    *,
    selector: AutomatedPolicySelector | None = None,
) -> DomainAction:
    """Route one automated choice through only its seat observation and actions."""

    seat = next((value for value in room.seats if value.seat_id == seat_id), None)
    if seat is None or not isinstance(seat.controller, AutomatedSeatController):
        raise ValueError("seat is not controlled by an automated policy")
    policies = StaticAutomatedPolicySelector() if selector is None else selector
    policy = policies.select(seat.controller.policy_id)
    observation = build_seat_observation(room, seat_id)
    return policy.choose_action(observation, legal_actions, rng)
