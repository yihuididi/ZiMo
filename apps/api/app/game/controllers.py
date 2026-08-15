"""Controller-facing policy ports; external seats deliberately have no chooser."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol

from .actions import DomainAction
from .model import PolicyId
from .observation import PlayerObservation
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
