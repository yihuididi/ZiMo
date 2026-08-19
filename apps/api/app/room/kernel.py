"""State, authentication, and persistence kernel for one room."""

from __future__ import annotations

import hmac
import json
import secrets
from collections.abc import Callable, Mapping, Sequence

from pydantic import ValidationError

if __package__.startswith("app."):
    from ..game import (
        Clock,
        ExternalSeatController,
        PlayerId,
        PublicRoomView,
        RoomState,
        RoomStatus,
        SystemClock,
        build_public_room_view,
        deserialize_room_state,
    )
    from ..lobby import LobbyTransition, catalog_lobby_actions
    from ..persistence import (
        LobbyAuditPayload,
        PlayerRecord,
        PlayerPresenceRecord,
        ProcessedCommandRecord,
        ProjectedAuditEvent,
        RevisionConflictError,
        RoomCredentialRecord,
        RoomNotFoundError,
        RoomRepository,
        SocketTicketRecord,
    )
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import (
        Clock,
        ExternalSeatController,
        PlayerId,
        PublicRoomView,
        RoomState,
        RoomStatus,
        SystemClock,
        build_public_room_view,
        deserialize_room_state,
    )
    from lobby import LobbyTransition, catalog_lobby_actions
    from persistence import (
        LobbyAuditPayload,
        PlayerRecord,
        PlayerPresenceRecord,
        ProcessedCommandRecord,
        ProjectedAuditEvent,
        RevisionConflictError,
        RoomCredentialRecord,
        RoomNotFoundError,
        RoomRepository,
        SocketTicketRecord,
    )

from .codec import (
    canonical_json,
    capability_hash,
    derive_rotated_invite,
    require_non_negative_int,
    require_text,
)
from .contracts import (
    CommandResult,
    CommandViewResult,
    DISCONNECT_GRACE_MS,
    RoomServiceError,
    SessionEndedResult,
)


class RoomKernel:
    """Own the mutable repository cache and atomic commit boundary."""

    def __init__(
        self,
        repository: RoomRepository,
        *,
        clock: Clock | None = None,
        credential_source: Callable[[], str] | None = None,
        id_source: Callable[[str], str] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = SystemClock() if clock is None else clock
        self._credential_source = credential_source or (
            lambda: secrets.token_urlsafe(32)
        )
        self._id_source = id_source or (
            lambda prefix: f"{prefix}_{secrets.token_hex(16)}"
        )
        self._cached_state: RoomState | None = None
        self._commit_generation = 0

    @property
    def cached_state(self) -> RoomState | None:
        return self._cached_state

    @property
    def commit_generation(self) -> int:
        return self._commit_generation

    def initialize_room(
        self,
        snapshot_json: str,
        *,
        players: Sequence[PlayerRecord] = (),
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        socket_tickets: Sequence[SocketTicketRecord] = (),
        player_presence: Sequence[PlayerPresenceRecord] = (),
        room_credentials: RoomCredentialRecord | None = None,
    ) -> RoomState:
        if not isinstance(snapshot_json, str):
            raise TypeError("snapshot_json must be a string")
        state = deserialize_room_state(snapshot_json)
        persisted = self._repository.create_room(
            state,
            players=players,
            events=events,
            processed_commands=processed_commands,
            socket_tickets=socket_tickets,
            player_presence=player_presence,
            room_credentials=room_credentials,
        )
        self._cached_state = persisted
        self._commit_generation += 1
        return persisted

    def load_room(self) -> RoomState | None:
        persisted = self._repository.load_room()
        self._cached_state = persisted
        return persisted

    def commit_room(
        self,
        state: RoomState,
        *,
        expected_revision: int,
        players: Sequence[PlayerRecord] | None = None,
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        socket_tickets: Sequence[SocketTicketRecord] = (),
        player_presence: Sequence[PlayerPresenceRecord] = (),
        upsert_player_presence: PlayerPresenceRecord | None = None,
        clear_player_presence: Sequence[tuple[str, int]] = (),
        room_credentials: RoomCredentialRecord | None = None,
    ) -> RoomState:
        persisted = self._repository.commit(
            state,
            expected_revision=expected_revision,
            players=players,
            events=events,
            processed_commands=processed_commands,
            socket_tickets=socket_tickets,
            player_presence=player_presence,
            upsert_player_presence=upsert_player_presence,
            clear_player_presence=clear_player_presence,
            room_credentials=room_credentials,
        )
        self._cached_state = persisted
        self._commit_generation += 1
        return persisted

    def _require_room(self) -> RoomState:
        state = self._repository.load_room()
        if state is None:
            raise RoomServiceError("roomNotFound", 404, "The room was not found.")
        self._cached_state = state
        return state

    def _authenticate(self, player_token: str) -> PlayerRecord:
        if not isinstance(player_token, str) or not player_token:
            raise RoomServiceError(
                "invalidPlayerToken", 401, "Authentication is invalid."
            )
        player = self._repository.authenticate_player(capability_hash(player_token))
        if player is None:
            raise RoomServiceError(
                "invalidPlayerToken", 401, "Authentication is invalid."
            )
        return player

    def _active_socket_identities(
        self,
        identities: Sequence[tuple[str, int]],
    ) -> tuple[tuple[str, int], ...]:
        normalized: set[tuple[str, int]] = set()
        for identity in identities:
            if type(identity) is not tuple or len(identity) != 2:
                raise TypeError(
                    "socket identities must be (player_id, auth_generation) tuples"
                )
            player_id = require_text(identity[0], "player_id")
            generation = require_non_negative_int(identity[1], "auth_generation")
            player = self._repository.get_player(player_id)
            if player is not None and player.auth_generation == generation:
                normalized.add((player_id, generation))
        return tuple(sorted(normalized))

    def _require_invite(self, invite_token: str) -> None:
        if not isinstance(invite_token, str) or not invite_token:
            raise RoomServiceError(
                "invalidInviteToken", 403, "The invite token is invalid."
            )
        credential = self._repository.load_room_credentials()
        actual = capability_hash(invite_token)
        if credential is None or not hmac.compare_digest(
            credential.invite_token_hash, actual
        ):
            raise RoomServiceError(
                "invalidInviteToken", 403, "The invite token is invalid."
            )

    def _view(self, state: RoomState, player_id: str, *, now_ms: int) -> PublicRoomView:
        actor = PlayerId(player_id)
        disconnected_players = {
            presence.player_id: (
                None
                if state.status in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}
                else presence.disconnect_expires_at_ms
            )
            for presence in self._repository.list_player_presence()
        }
        return build_public_room_view(
            state,
            actor,
            server_time_ms=now_ms,
            actions=tuple(
                item.descriptor
                for item in catalog_lobby_actions(
                    state,
                    actor,
                    viewer_connected=str(actor) not in disconnected_players,
                )
            ),
            disconnected_players=disconnected_players,
            presence_version=self._repository.presence_version(),
        )

    def _player_is_connected(self, player_id: str) -> bool:
        return all(
            presence.player_id != player_id
            for presence in self._repository.list_player_presence()
        )

    def _new_player_record(
        self, state: RoomState, player_id: str, player_token: str, *, now_ms: int
    ) -> PlayerRecord:
        player = next(
            value for value in state.players if str(value.player_id) == player_id
        )
        seat = next(
            value
            for value in state.seats
            if isinstance(value.controller, ExternalSeatController)
            and str(value.controller.player_id) == player_id
        )
        return PlayerRecord(
            player_id=player_id,
            seat_id=str(seat.seat_id),
            display_name=player.display_name,
            role=player.role.value,
            controller_json=seat.controller.canonical_json(),
            token_hash=capability_hash(player_token),
            auth_generation=0,
            joined_at_ms=player.joined_at_ms,
            updated_at_ms=max(now_ms, player.joined_at_ms),
        )

    @staticmethod
    def _initial_presence(player_id: str, *, now_ms: int) -> PlayerPresenceRecord:
        return PlayerPresenceRecord(
            player_id=player_id,
            auth_generation=0,
            disconnected_at_ms=now_ms,
            disconnect_expires_at_ms=now_ms + DISCONNECT_GRACE_MS,
        )

    def _player_records_for_state(
        self,
        state: RoomState,
        *,
        new_tokens: Mapping[str, str] | None = None,
    ) -> tuple[PlayerRecord, ...]:
        existing = self._repository.list_player_records(include_revoked=True)
        existing_by_id = {record.player_id: record for record in existing}
        tokens = {} if new_tokens is None else dict(new_tokens)
        records: list[PlayerRecord] = [
            record for record in existing if record.left_at_ms is not None
        ]
        for player in state.players:
            player_id = str(player.player_id)
            seat = next(
                value
                for value in state.seats
                if isinstance(value.controller, ExternalSeatController)
                and value.controller.player_id == player.player_id
            )
            previous = existing_by_id.get(player_id)
            if previous is None:
                raw = tokens.get(player_id)
                if raw is None:
                    raise RuntimeError("new room player is missing credential material")
                token_hash = capability_hash(raw)
                generation = 0
            else:
                token_hash = previous.token_hash
                generation = previous.auth_generation
            records.append(
                PlayerRecord(
                    player_id=player_id,
                    seat_id=str(seat.seat_id),
                    display_name=player.display_name,
                    role=player.role.value,
                    controller_json=seat.controller.canonical_json(),
                    token_hash=token_hash,
                    auth_generation=generation,
                    joined_at_ms=player.joined_at_ms,
                    updated_at_ms=max(
                        state.updated_at_ms,
                        0 if previous is None else previous.updated_at_ms,
                    ),
                )
            )
        return tuple(records)

    def _audit_event(
        self, state: RoomState, event_type: str, details: Mapping[str, object]
    ) -> ProjectedAuditEvent:
        return ProjectedAuditEvent(
            payload=LobbyAuditPayload(
                event_type=event_type,
                room_id=str(state.room_id),
                revision=state.revision,
                details_json=canonical_json(dict(details)),
            ),
            created_at_ms=state.updated_at_ms,
        )

    def _transition_events(
        self, transition: LobbyTransition
    ) -> tuple[ProjectedAuditEvent, ...]:
        values = (
            (transition.event_type, transition.event_details),
        ) + transition.additional_events
        return tuple(
            self._audit_event(transition.state, event_type, details)
            for event_type, details in values
        )

    def _commit(
        self,
        state: RoomState,
        *,
        expected_revision: int,
        players: Sequence[PlayerRecord] | None = None,
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        player_presence: Sequence[PlayerPresenceRecord] = (),
        upsert_player_presence: PlayerPresenceRecord | None = None,
        clear_player_presence: Sequence[tuple[str, int]] = (),
        room_credentials: RoomCredentialRecord | None = None,
    ) -> RoomState:
        try:
            persisted = self._repository.commit(
                state,
                expected_revision=expected_revision,
                players=players,
                events=events,
                processed_commands=processed_commands,
                player_presence=player_presence,
                upsert_player_presence=upsert_player_presence,
                clear_player_presence=clear_player_presence,
                room_credentials=room_credentials,
            )
        except RevisionConflictError as exc:
            raise RoomServiceError(
                "revisionConflict",
                409,
                "The room revision is stale.",
                current_revision=exc.actual_revision,
            ) from exc
        except RoomNotFoundError as exc:
            raise RoomServiceError(
                "roomNotFound", 404, "The room was not found."
            ) from exc
        self._cached_state = persisted
        self._commit_generation += 1
        return persisted

    def _replay_result(
        self, command: ProcessedCommandRecord, player_token: str
    ) -> CommandResult:
        try:
            stored = json.loads(command.result_json)
            if type(stored) is not dict or set(stored) != {"result", "rotatedInvite"}:
                raise ValueError("invalid stored command envelope")
            result_value = stored["result"]
            if type(result_value) is not dict:
                raise ValueError("invalid stored command result")
            encoded = canonical_json(result_value)
            if result_value.get("type") == "view":
                result: CommandResult = CommandViewResult.model_validate_json(
                    encoded, strict=True
                )
            elif result_value.get("type") == "sessionEnded":
                result = SessionEndedResult.model_validate_json(encoded, strict=True)
            else:
                raise ValueError("invalid stored command result type")
            rotated = stored["rotatedInvite"]
            if type(rotated) is not bool:
                raise ValueError("invalid stored rotation flag")
        except (TypeError, ValueError, ValidationError) as exc:
            raise RuntimeError("stored command result is corrupt") from exc
        if rotated:
            if not isinstance(result, CommandViewResult):
                raise RuntimeError("stored invite rotation result is corrupt")
            state = self._require_room()
            invite = derive_rotated_invite(
                player_token,
                str(state.room_id),
                command.player_id,
                command.command_id,
            )
            result = result.model_copy(update={"invite_token": invite})
        return result

    def _new_capability(self) -> str:
        value = self._credential_source()
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        if (
            not isinstance(value, str)
            or len(value) != 43
            or any(character not in alphabet for character in value)
        ):
            raise RuntimeError("credential source returned an invalid capability")
        return value

    def _new_id(self, prefix: str) -> str:
        return require_text(self._id_source(prefix), f"{prefix}_id")

    def _now_ms(self) -> int:
        return require_non_negative_int(self._clock.now_ms(), "clock.now_ms")


__all__ = ["RoomKernel"]
