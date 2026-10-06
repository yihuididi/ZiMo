"""Gameplay catalogues, deadlines, and bot continuation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

if __package__.startswith("app."):
    from ..game import (
        MAX_AUTOMATED_CONTINUATIONS,
        AutomatedDecisionRequested,
        AutomatedSeatController,
        BonusExposed,
        ClaimWindowRequested,
        Discard,
        Chow,
        Pong,
        Kong,
        Pass,
        DeclareWin,
        FinishHand,
        DiscardClaimsPhase,
        KongRobberyPhase,
        DiscardWindowResolved,
        MeldDeclared,
        PublicTileView,
        DomainAction,
        DomainEvent,
        HandCompleted,
        FlowerTransferred,
        WinDeclared,
        HandOutcome,
        HandSetupCompleted,
        MatchCompletionRequested,
        OpaqueActionDescriptor,
        PendingDeadline,
        PlayerId,
        RoomState,
        SeatId,
        TileDiscarded,
        TransitionResult,
        build_seat_observation,
        rules_for_id,
        finalize_completed_hand,
    )
    from ..persistence import GameplayAuditPayload, ProjectedAuditEvent
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import (
        MAX_AUTOMATED_CONTINUATIONS,
        AutomatedDecisionRequested,
        AutomatedSeatController,
        BonusExposed,
        ClaimWindowRequested,
        Discard,
        Chow,
        Pong,
        Kong,
        Pass,
        DeclareWin,
        FinishHand,
        DiscardClaimsPhase,
        KongRobberyPhase,
        DiscardWindowResolved,
        MeldDeclared,
        PublicTileView,
        DomainAction,
        DomainEvent,
        HandCompleted,
        FlowerTransferred,
        WinDeclared,
        HandOutcome,
        HandSetupCompleted,
        MatchCompletionRequested,
        OpaqueActionDescriptor,
        PendingDeadline,
        PlayerId,
        RoomState,
        SeatId,
        TileDiscarded,
        TransitionResult,
        build_seat_observation,
        rules_for_id,
        finalize_completed_hand,
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

        result = self._engine_for(state).resolve_discard_window(state, deadline.window_id)
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
                next_state, domain_events, previous_state=state, created_at_ms=now_ms
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
        return rules_for_id(state.ruleset_id).capabilities

    def _catalog_gameplay_actions(
        self, state: RoomState, player_id: str
    ) -> tuple[_CataloguedGameplayAction, ...]:
        seat_id = self._external_seat_id(state, player_id)
        if seat_id is None:
            return ()
        actions = self._engine_for(state).legal_actions(state, seat_id)
        return tuple(self._catalog_action(state, seat_id, action) for action in actions)

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
        result = self._engine_for(state).transition(state, action)
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
        result = self._engine_for(state).setup_match(state)
        next_state, events = self._pump_gameplay(result, now_ms=now_ms)
        # Lobby start already assigned the one revision for this command.
        hand = next_state.match.current_hand
        if isinstance(hand.phase, (DiscardClaimsPhase, KongRobberyPhase)):
            phase = hand.phase.model_copy(update={"opening_revision": state.revision})
            hand = hand.model_copy(update={"phase": phase})
            next_state = self._validated_state_update(
                next_state,
                match=next_state.match.model_copy(update={"current_hand": hand}),
            )
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
                    raise RuntimeError("claim windows must last 3000 ms")
                if state.pending_deadline is not None:
                    raise RuntimeError(
                        "gameplay transition attempted to extend a deadline"
                    )
                state = self._validated_state_update(
                    state,
                    pending_deadline=PendingDeadline(
                        window_id=effect.window_id,
                        deadline_ms=now_ms + effect.duration_ms,
                    ),
                )
                # Choose every bot intent before the opening snapshot is committed.
                for seat_id in effect.eligible_seat_ids:
                    seat = next(s for s in state.seats if s.seat_id == seat_id)
                    if isinstance(seat.controller, AutomatedSeatController):
                        chosen = self._choose_automated_action(state, seat_id)
                        response = self._engine_for(state).transition(state, chosen)
                        state = response.state
                        events.extend(response.domain_events)
                effects = ()
                continue

            if isinstance(effect, MatchCompletionRequested):
                state = finalize_completed_hand(
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
            result = self._engine_for(state).transition(state, action)
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
        legal_actions = self._engine_for(state).legal_actions(state, seat_id)
        observation = build_seat_observation(
            state,
            seat_id,
            capabilities=self._capabilities(state),
        )
        policy = self._policy_selector.select(seat.controller.policy_id)
        chosen = policy.choose_action(observation, legal_actions, self._random_source)
        if not any(chosen == legal for legal in legal_actions):
            raise RuntimeError(
                "automated policy returned an action outside its catalog"
            )
        return chosen

    def _claim_revision_valid(
        self, state: RoomState, player_id: str, action_id: str, expected_revision: int
    ) -> bool:
        hand = state.match.current_hand if state.match else None
        if (
            hand is None
            or not isinstance(hand.phase, (DiscardClaimsPhase, KongRobberyPhase))
        ):
            return False
        opening = hand.phase.opening_revision
        return (
            opening is not None
            and opening <= expected_revision <= state.revision
            and any(
                item.descriptor.action_id == action_id
                for item in self._catalog_gameplay_actions(state, player_id)
            )
        )

    def _catalog_action(
        self, state: RoomState, seat_id: SeatId, action: DomainAction
    ) -> _CataloguedGameplayAction:
        if isinstance(action, Discard):
            return self._catalog_discard(state, seat_id, action)
        hand = state.match.current_hand
        player = next(p for p in hand.player_hands if p.seat_id == seat_id)
        held = (
            *player.concealed_tiles,
            *((player.drawn_tile,) if player.drawn_tile else ()),
        )
        tiles = tuple(
            PublicTileView(face=t.face)
            for t in held
            if t.tile_id in getattr(action, "tile_ids", ())
        )
        label = (
            "Kong-3"
            if isinstance(action, Kong) and action.kind.value == "KONG_3"
            else (
                "Kong-1" if isinstance(action, Kong) and action.kind.value == "KONG_1" else "Kong-4"
                if isinstance(action, Kong)
                else (
                    "Game" if isinstance(action, DeclareWin) else
                    "Finish Hand"
                    if isinstance(action, FinishHand)
                    else action.type.title()
                )
            )
        )
        return _CataloguedGameplayAction(
            descriptor=OpaqueActionDescriptor(
                action_id=self._gameplay_action_id(state, seat_id, action),
                label=label,
                tiles=tiles,
                presentation_slot=(
                    "claimActions"
                    if isinstance(hand.phase, (DiscardClaimsPhase, KongRobberyPhase))
                    else "turnActions"
                ),
            ),
            action=action,
        )

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
                "revision": (
                    state.match.current_hand.phase.opening_revision
                    if isinstance(state.match.current_hand.phase, (DiscardClaimsPhase, KongRobberyPhase))
                    else state.revision
                ),
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
        previous_state: RoomState,
        created_at_ms: int,
    ) -> tuple[ProjectedAuditEvent, ...]:
        projected: list[ProjectedAuditEvent] = []
        previous_hand = previous_state.match.current_hand if previous_state.match else None
        current_hand = state.match.current_hand if state.match else None
        prior_count = len(previous_hand.payments) if previous_hand else 0
        new_payments = current_hand.payments[prior_count:] if current_hand else ()
        def add_public(event_type: str, details: dict[str, object]) -> None:
            projected.append(ProjectedAuditEvent(
                payload=GameplayAuditPayload(
                    event_type=event_type, room_id=str(state.room_id),
                    revision=state.revision, details_json=canonical_json(details),
                ), created_at_ms=created_at_ms,
            ))
        def add_payments() -> None:
            for payment in new_payments:
                add_public("paymentMade", {
                    "sequence": payment.sequence,
                    "payerSeatId": str(payment.payer_seat_id),
                    "recipientSeatId": str(payment.recipient_seat_id),
                    "amount": payment.amount,
                    "reason": payment.reason,
                })
        emitted_payments = False
        for event in domain_events:
            if isinstance(event, HandCompleted) and not emitted_payments:
                add_payments()
                emitted_payments = True
            public = _project_gameplay_event(event)
            if public is None:
                continue
            event_type, details = public
            add_public(event_type, details)
        if not emitted_payments:
            add_payments()
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
    if isinstance(event, FlowerTransferred):
        return "flowerTransferred", {
            "fromSeatId": str(event.from_seat_id),
            "toSeatId": str(event.to_seat_id),
            "tileFamily": event.tile.face.family.value,
            "tileValue": event.tile.face.value,
        }
    if isinstance(event, DiscardWindowResolved) and event.winning_seat_id is not None:
        return "claimResolved", {
            "discardSequence": event.discard_sequence,
            "seatId": str(event.winning_seat_id),
            "claimKind": event.claim_kind.value,
        }
    if isinstance(event, MeldDeclared):
        return "meldDeclared", {
            "seatId": str(event.seat_id),
            "kind": event.meld.kind.value,
            "kongKind": event.meld.kong_kind,
            "tiles": [
                PublicTileView(face=t.face).canonical_data() for t in event.meld.tiles
            ],
            "claimedFromSeatId": event.meld.claimed_from_seat_id,
            "discardSequence": event.meld.discard_sequence,
        }
    if isinstance(event, HandCompleted):
        return "handCompleted", {
            "outcome": event.result.outcome.value,
            "winnerSeatId": event.result.winner_seat_id,
            "providerSeatId": event.result.provider_seat_id,
            "winSource": event.result.win_source.value if event.result.win_source else None,
            "fan": event.result.fan,
            "cappedFan": event.result.capped_fan,
            "payoutBase": event.result.payout_base,
            "reason": event.result.reason,
        }
    # TileDrawn and discard-window mechanics are deliberately not public audit
    # facts. The individualized room projection carries only their safe result.
    return None


def _tile_face_label(family: str, value: int | str) -> str:
    family_label = family.replace("_", " ").title()
    return f"{family_label} {value}"


__all__ = ["DISCARD_WINDOW_MS", "RoomGameplay"]
