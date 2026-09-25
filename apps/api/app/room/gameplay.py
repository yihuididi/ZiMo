"""Ruleset-versioned gameplay catalogues, deadlines, and bot continuation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

if __package__.startswith("app."):
    from ..game import (
        MAX_AUTOMATED_CONTINUATIONS,
        MILESTONE_3_RULESET_VERSION,
        AutomatedDecisionRequested,
        AutomatedSeatController,
        BonusExposed,
        ClaimWindowRequested,
        Discard,
        DomainAction,
        DomainEvent,
        HandCompleted,
        HandOutcome,
        HandSetupCompleted,
        MatchCompletionRequested,
        MilestoneThreeEngine,
        OpaqueActionDescriptor,
        PendingDeadline,
        PlayerId,
        RoomState,
        SeatId,
        TileDiscarded,
        TransitionResult,
        build_seat_observation,
        capabilities_for_ruleset_version,
        finalize_completed_preview,
    )
    from ..persistence import GameplayAuditPayload, ProjectedAuditEvent
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import (
        MAX_AUTOMATED_CONTINUATIONS,
        MILESTONE_3_RULESET_VERSION,
        AutomatedDecisionRequested,
        AutomatedSeatController,
        BonusExposed,
        ClaimWindowRequested,
        Discard,
        DomainAction,
        DomainEvent,
        HandCompleted,
        HandOutcome,
        HandSetupCompleted,
        MatchCompletionRequested,
        MilestoneThreeEngine,
        OpaqueActionDescriptor,
        PendingDeadline,
        PlayerId,
        RoomState,
        SeatId,
        TileDiscarded,
        TransitionResult,
        build_seat_observation,
        capabilities_for_ruleset_version,
        finalize_completed_preview,
    )
    from persistence import GameplayAuditPayload, ProjectedAuditEvent

from .codec import canonical_json, require_non_negative_int, require_text
from .contracts import RoomServiceError


DISCARD_WINDOW_MS = 3_000


@dataclass(frozen=True, slots=True)
class _CataloguedGameplayAction:
    descriptor: OpaqueActionDescriptor
    action: DomainAction


class RoomGameplay:
    """Gameplay-side use cases layered on a :class:`RoomKernel`."""

    def advance_due(self, now_ms: int | None = None) -> bool:
        """Idempotently resolve the active window at its exact deadline."""

        timestamp = self._now_ms() if now_ms is None else now_ms
        require_non_negative_int(timestamp, "now_ms")
        return self._advance_due_at(timestamp)

    def _advance_due_at(self, now_ms: int) -> bool:
        state = self._repository.load_room()
        if state is None:
            self._cached_state = None
            return False
        self._cached_state = state
        deadline = state.pending_deadline
        if deadline is None or now_ms < deadline.deadline_ms:
            return False
        if str(state.ruleset_version) != MILESTONE_3_RULESET_VERSION:
            raise RuntimeError("a non-preview room retained a gameplay deadline")

        result = self._game_engine.resolve_discard_window(
            state, deadline.window_id
        )
        result = TransitionResult(
            state=self._validated_state_update(
                result.state,
                pending_deadline=None,
            ),
            domain_events=result.domain_events,
            effects=result.effects,
        )
        next_state, domain_events = self._pump_gameplay(result, now_ms=now_ms)
        next_state = self._finalize_origin_state(
            next_state,
            previous_revision=state.revision,
            now_ms=now_ms,
        )
        self._commit(
            next_state,
            expected_revision=state.revision,
            events=self._gameplay_audit_events(
                next_state, domain_events, created_at_ms=now_ms
            ),
        )
        return True

    def next_gameplay_alarm_ms(self) -> int | None:
        state = self._repository.load_room()
        if state is None or state.pending_deadline is None:
            return None
        return state.pending_deadline.deadline_ms

    def next_alarm_ms(self) -> int | None:
        deadlines = tuple(
            value
            for value in (
                self.next_presence_alarm_ms(),
                self.next_gameplay_alarm_ms(),
            )
            if value is not None
        )
        return min(deadlines) if deadlines else None

    def _capabilities(self, state: RoomState) -> tuple[object, ...]:
        return capabilities_for_ruleset_version(str(state.ruleset_version))

    def _catalog_gameplay_actions(
        self, state: RoomState, player_id: str
    ) -> tuple[_CataloguedGameplayAction, ...]:
        if str(state.ruleset_version) != MILESTONE_3_RULESET_VERSION:
            return ()
        seat_id = self._external_seat_id(state, player_id)
        if seat_id is None:
            return ()
        actions = self._game_engine.legal_actions(state, seat_id)
        return tuple(
            self._catalog_discard(state, seat_id, action)
            for action in actions
            if isinstance(action, Discard)
        )

    def _resolve_gameplay_action(
        self,
        state: RoomState,
        player_id: str,
        action_id: str,
    ) -> DomainAction:
        require_text(action_id, "action_id")
        for item in self._catalog_gameplay_actions(state, player_id):
            if item.descriptor.action_id == action_id:
                return item.action
        raise RoomServiceError(
            "actionNotAvailable",
            409,
            "The action is not available.",
            current_revision=state.revision,
        )

    def _apply_gameplay_action(
        self,
        state: RoomState,
        action: DomainAction,
        *,
        now_ms: int,
    ) -> tuple[RoomState, tuple[DomainEvent, ...]]:
        result = self._game_engine.transition(state, action)
        next_state, events = self._pump_gameplay(result, now_ms=now_ms)
        return (
            self._finalize_origin_state(
                next_state,
                previous_revision=state.revision,
                now_ms=now_ms,
            ),
            events,
        )

    def _setup_started_match(
        self,
        state: RoomState,
        *,
        now_ms: int,
    ) -> tuple[RoomState, tuple[DomainEvent, ...]]:
        if str(state.ruleset_version) != MILESTONE_3_RULESET_VERSION:
            return state, ()
        result = self._game_engine.setup_match(state)
        next_state, events = self._pump_gameplay(result, now_ms=now_ms)
        # Lobby start already assigned the one revision for this command.
        return (
            self._validated_state_update(
                next_state,
                revision=state.revision,
                updated_at_ms=max(now_ms, state.updated_at_ms),
            ),
            events,
        )

    def _pump_gameplay(
        self,
        initial: TransitionResult,
        *,
        now_ms: int,
    ) -> tuple[RoomState, tuple[DomainEvent, ...]]:
        """Consume room-owned effects without exposing an intermediate state."""

        state = initial.state
        events: list[DomainEvent] = list(initial.domain_events)
        effects = initial.effects
        automated_continuations = 0
        while effects:
            control_effects = tuple(
                effect
                for effect in effects
                if isinstance(
                    effect,
                    (
                        ClaimWindowRequested,
                        AutomatedDecisionRequested,
                        MatchCompletionRequested,
                    ),
                )
            )
            if len(control_effects) != len(effects) or len(control_effects) != 1:
                raise RuntimeError("gameplay transition emitted conflicting effects")
            effect = control_effects[0]

            if isinstance(effect, ClaimWindowRequested):
                if effect.duration_ms != DISCARD_WINDOW_MS:
                    raise RuntimeError("preview discard windows must last 3000 ms")
                if state.pending_deadline is not None:
                    raise RuntimeError("gameplay transition attempted to extend a deadline")
                state = self._validated_state_update(
                    state,
                    pending_deadline=PendingDeadline(
                        window_id=effect.window_id,
                        deadline_ms=now_ms + effect.duration_ms,
                    ),
                )
                effects = ()
                continue

            if isinstance(effect, MatchCompletionRequested):
                state = finalize_completed_preview(
                    self._validated_state_update(state, pending_deadline=None),
                    completed_at_ms=now_ms,
                )
                effects = ()
                continue

            if automated_continuations >= MAX_AUTOMATED_CONTINUATIONS:
                raise RuntimeError("automated gameplay continuation limit exceeded")
            automated_continuations += 1
            before = state.canonical_json()
            action = self._choose_automated_action(state, effect.seat_id)
            result = self._game_engine.transition(state, action)
            if result.state.canonical_json() == before:
                raise RuntimeError("automated gameplay transition made no progress")
            state = result.state
            events.extend(result.domain_events)
            effects = result.effects

        return state, tuple(events)

    def _choose_automated_action(
        self, state: RoomState, seat_id: SeatId
    ) -> DomainAction:
        seat = next(
            (value for value in state.seats if value.seat_id == seat_id),
            None,
        )
        if seat is None or not isinstance(seat.controller, AutomatedSeatController):
            raise RuntimeError("automated decision references a non-automated seat")
        legal_actions = self._game_engine.legal_actions(state, seat_id)
        observation = build_seat_observation(
            state,
            seat_id,
            capabilities=self._capabilities(state),
        )
        policy = self._policy_selector.select(seat.controller.policy_id)
        chosen = policy.choose_action(observation, legal_actions, self._random_source)
        if not any(chosen == legal for legal in legal_actions):
            raise RuntimeError("automated policy returned an action outside its catalog")
        return chosen

    def _catalog_discard(
        self,
        state: RoomState,
        seat_id: SeatId,
        action: Discard,
    ) -> _CataloguedGameplayAction:
        hand = state.match.current_hand if state.match is not None else None
        player_hand = next(
            (
                value
                for value in (() if hand is None else hand.player_hands)
                if value.seat_id == seat_id
            ),
            None,
        )
        if player_hand is None:
            raise RuntimeError("legal discard references a seat without a hand")
        if (
            player_hand.drawn_tile is not None
            and player_hand.drawn_tile.tile_id == action.tile_id
        ):
            tile = player_hand.drawn_tile
            slot = "drawnTile"
            presentation_index = None
        else:
            indexed = next(
                (
                    (index, tile)
                    for index, tile in enumerate(player_hand.concealed_tiles)
                    if tile.tile_id == action.tile_id
                ),
                None,
            )
            if indexed is None:
                raise RuntimeError("legal discard references an unheld tile")
            presentation_index, tile = indexed
            slot = "concealedTile"
        descriptor = OpaqueActionDescriptor(
            action_id=self._gameplay_action_id(state, seat_id, action),
            label=f"Discard {_tile_face_label(tile.face.family.value, tile.face.value)}",
            tone="primary",
            presentation_slot=slot,
            presentation_index=presentation_index,
        )
        return _CataloguedGameplayAction(descriptor=descriptor, action=action)

    @staticmethod
    def _gameplay_action_id(
        state: RoomState, seat_id: SeatId, action: DomainAction
    ) -> str:
        material = canonical_json(
            {
                "action": action.canonical_data(),
                "revision": state.revision,
                "roomId": str(state.room_id),
                "seatId": str(seat_id),
                "version": 1,
            }
        ).encode()
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _external_seat_id(state: RoomState, player_id: str) -> SeatId | None:
        actor = PlayerId(player_id)
        return next(
            (
                seat.seat_id
                for seat in state.seats
                if getattr(seat.controller, "type", None) == "external"
                and seat.controller.player_id == actor
            ),
            None,
        )

    @staticmethod
    def _validated_state_update(state: RoomState, **updates: object) -> RoomState:
        candidate = state.model_copy(update=updates)
        return RoomState.model_validate_json(candidate.canonical_json(), strict=True)

    def _finalize_origin_state(
        self,
        state: RoomState,
        *,
        previous_revision: int,
        now_ms: int,
    ) -> RoomState:
        return self._validated_state_update(
            state,
            revision=previous_revision + 1,
            updated_at_ms=max(now_ms, state.updated_at_ms),
        )

    def _gameplay_audit_events(
        self,
        state: RoomState,
        domain_events: tuple[DomainEvent, ...],
        *,
        created_at_ms: int,
    ) -> tuple[ProjectedAuditEvent, ...]:
        projected: list[ProjectedAuditEvent] = []
        for event in domain_events:
            public = _project_gameplay_event(event)
            if public is None:
                continue
            event_type, details = public
            projected.append(
                ProjectedAuditEvent(
                    payload=GameplayAuditPayload(
                        event_type=event_type,
                        room_id=str(state.room_id),
                        revision=state.revision,
                        details_json=canonical_json(details),
                    ),
                    created_at_ms=created_at_ms,
                )
            )
        return tuple(projected)


def _project_gameplay_event(
    event: DomainEvent,
) -> tuple[str, dict[str, object]] | None:
    if isinstance(event, HandSetupCompleted):
        return "handStarted", {"handId": str(event.hand_id)}
    if isinstance(event, BonusExposed):
        return "bonusExposed", {
            "initial": event.initial,
            "seatId": str(event.seat_id),
            "tileFamily": event.tile.face.family.value,
            "tileValue": event.tile.face.value,
        }
    if isinstance(event, TileDiscarded):
        return "tileDiscarded", {
            "discardSequence": event.discard_sequence,
            "seatId": str(event.seat_id),
            "tileFamily": event.tile.face.family.value,
            "tileValue": event.tile.face.value,
        }
    if isinstance(event, HandCompleted):
        if event.result.outcome is not HandOutcome.TIE:
            raise RuntimeError("the draw/discard preview may only complete as a tie")
        if event.result.reason != "LIVE_WALL_EXHAUSTED":
            raise RuntimeError("the preview tie reason is not allow-listed")
        return "previewTied", {
            "outcome": event.result.outcome.value,
            "reason": event.result.reason,
        }
    # TileDrawn and discard-window mechanics are deliberately not public audit
    # facts. The individualized room projection carries only their safe result.
    return None


def _tile_face_label(family: str, value: int | str) -> str:
    family_label = family.replace("_", " ").title()
    return f"{family_label} {value}"


__all__ = ["DISCARD_WINDOW_MS", "RoomGameplay"]
