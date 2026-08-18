"""Platform-neutral orchestration for one authoritative Mahjong room."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, TypeAlias

from pydantic import Field, ValidationError

if __package__:
    from .game import (
        Clock,
        ExternalSeatController,
        GameConfig,
        GameModel,
        PlayerId,
        PublicRoomView,
        RoomState,
        RoomStatus,
        SystemClock,
        build_public_room_view,
        deserialize_room_state,
    )
    from .lobby import (
        LobbyDomainError,
        LobbyTransition,
        apply_lobby_disconnect,
        apply_lobby_action,
        authorize_lobby_config,
        catalog_lobby_actions,
        create_lobby_room,
        expire_disconnected_lobby_player,
        join_lobby_room,
        reconcile_lobby_host,
        resolve_lobby_action,
        update_lobby_config,
    )
    from .persistence import (
        LobbyAuditPayload,
        PlayerRecord,
        PlayerPresenceRecord,
        ProcessedCommandConflictError,
        ProcessedCommandRecord,
        ProjectedAuditEvent,
        RevisionConflictError,
        RoomAlreadyExistsError,
        RoomCredentialRecord,
        RoomInitializedAuditPayload,
        RoomNotFoundError,
        RoomRepository,
        RoomStateCommittedAuditPayload,
        SocketTicketRecord,
        SocketTicketUnavailableError,
        StoredAuditEvent,
    )
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import (
        Clock,
        ExternalSeatController,
        GameConfig,
        GameModel,
        PlayerId,
        PublicRoomView,
        RoomState,
        RoomStatus,
        SystemClock,
        build_public_room_view,
        deserialize_room_state,
    )
    from lobby import (
        LobbyDomainError,
        LobbyTransition,
        apply_lobby_disconnect,
        apply_lobby_action,
        authorize_lobby_config,
        catalog_lobby_actions,
        create_lobby_room,
        expire_disconnected_lobby_player,
        join_lobby_room,
        reconcile_lobby_host,
        resolve_lobby_action,
        update_lobby_config,
    )
    from persistence import (
        LobbyAuditPayload,
        PlayerRecord,
        PlayerPresenceRecord,
        ProcessedCommandConflictError,
        ProcessedCommandRecord,
        ProjectedAuditEvent,
        RevisionConflictError,
        RoomAlreadyExistsError,
        RoomCredentialRecord,
        RoomInitializedAuditPayload,
        RoomNotFoundError,
        RoomRepository,
        RoomStateCommittedAuditPayload,
        SocketTicketRecord,
        SocketTicketUnavailableError,
        StoredAuditEvent,
    )


SOCKET_TICKET_TTL_MS = 30_000
DISCONNECT_GRACE_MS = 300_000
_INVITE_ROTATION_DOMAIN = b"zimo:invite-rotation:v1\x00"


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


class RoomOrchestrator:
    """Authenticate, transition, and atomically persist one room."""

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

    def create_room(self, room_id: str, display_name: str) -> RoomCreation:
        now_ms = self._now_ms()
        player_id = self._new_id("player")
        player_token = self._new_capability()
        invite_token = self._new_capability()
        try:
            state = create_lobby_room(room_id, player_id, display_name, now_ms=now_ms)
            player_record = self._new_player_record(
                state, player_id, player_token, now_ms=now_ms
            )
            credential = RoomCredentialRecord(
                invite_token_hash=_capability_hash(invite_token),
                invite_generation=0,
                created_at_ms=now_ms,
                updated_at_ms=now_ms,
            )
            persisted = self._repository.create_room(
                state,
                players=(player_record,),
                events=(
                    self._audit_event(
                        state, "roomCreated", {"hostPlayerId": player_id}
                    ),
                ),
                player_presence=(
                    self._initial_presence(player_id, now_ms=now_ms),
                ),
                room_credentials=credential,
            )
        except LobbyDomainError as exc:
            raise _lobby_service_error(exc) from exc
        except RoomAlreadyExistsError as exc:
            raise RoomServiceError(
                "roomAlreadyExists", 409, "The room already exists."
            ) from exc
        self._cached_state = persisted
        self._commit_generation += 1
        return RoomCreation(
            room_id=str(persisted.room_id),
            player_id=player_id,
            player_token=player_token,
            invite_token=invite_token,
            view=self._view(persisted, player_id, now_ms=now_ms),
        )

    def join_room(self, invite_token: str, display_name: str) -> PlayerSession:
        state = self._require_room()
        self._require_invite(invite_token)
        now_ms = self._now_ms()
        player_id = self._new_id("player")
        player_token = self._new_capability()
        try:
            transition = join_lobby_room(
                state, player_id, display_name, now_ms=now_ms
            )
        except LobbyDomainError as exc:
            raise _lobby_service_error(exc, current_revision=state.revision) from exc
        persisted = self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(
                transition.state, new_tokens={player_id: player_token}
            ),
            events=self._transition_events(transition),
            player_presence=(
                self._initial_presence(player_id, now_ms=now_ms),
            ),
        )
        return PlayerSession(
            room_id=str(persisted.room_id),
            player_id=player_id,
            player_token=player_token,
            view=self._view(persisted, player_id, now_ms=now_ms),
        )

    def authenticated_view(self, player_token: str) -> PublicRoomView:
        player = self._authenticate(player_token)
        return self._view(
            self._require_room(), player.player_id, now_ms=self._now_ms()
        )

    def authenticate_room_player(self, player_token: str) -> AuthenticatedPlayer:
        """Authenticate for transport preflight without projecting a room view."""

        self._require_room()
        player = self._authenticate(player_token)
        return AuthenticatedPlayer(
            player_id=player.player_id,
            auth_generation=player.auth_generation,
        )

    def view_for_player_id(
        self, player_id: str, auth_generation: int | None = None
    ) -> PublicRoomView:
        player = self._repository.get_player(player_id)
        if player is None or (
            auth_generation is not None and player.auth_generation != auth_generation
        ):
            raise RoomServiceError(
                "invalidPlayerToken", 401, "Authentication is invalid."
            )
        return self._view(
            self._require_room(), player.player_id, now_ms=self._now_ms()
        )

    def active_socket_identity(self, player_id: str, auth_generation: int) -> bool:
        player = self._repository.get_player(player_id)
        return player is not None and player.auth_generation == auth_generation

    def player_connected(self, player_id: str, auth_generation: int) -> bool:
        """Reconcile one authenticated socket connection."""

        requested = (_require_text(player_id, "player_id"), auth_generation)
        _require_non_negative_int(auth_generation, "auth_generation")
        disconnected = {
            (presence.player_id, presence.auth_generation)
            for presence in self._repository.list_player_presence()
        }
        connected = {
            (record.player_id, record.auth_generation)
            for record in self._repository.list_player_records(
                include_revoked=False
            )
            if (record.player_id, record.auth_generation) not in disconnected
        }
        connected.add(requested)
        return self.reconcile_socket_presence(tuple(sorted(connected)))

    def reconcile_socket_presence(
        self,
        connected_identities: Sequence[tuple[str, int]],
    ) -> bool:
        """Atomically reconcile a batch of live sockets and any host handoff."""

        connected = self._active_socket_identities(connected_identities)
        if not connected:
            return False
        state = self._require_room()
        connected_player_ids = {
            PlayerId(player_id) for player_id, _generation in connected
        }
        transition = None
        if state.status not in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
            transition = reconcile_lobby_host(
                state,
                connected_player_ids,
                now_ms=self._now_ms(),
            )
        if transition is None:
            return self._repository.set_players_connected(connected)
        self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(transition.state),
            events=self._transition_events(transition),
            clear_player_presence=connected,
        )
        return True

    def player_disconnected(
        self,
        player_id: str,
        auth_generation: int,
        connected_identities: Sequence[tuple[str, int]] | None = None,
    ) -> bool:
        """Persist a final-socket close and its canonical lobby consequences."""

        _require_text(player_id, "player_id")
        _require_non_negative_int(auth_generation, "auth_generation")
        player = self._repository.get_player(player_id)
        if player is None or player.auth_generation != auth_generation:
            return False
        if any(
            presence.player_id == player_id
            and presence.auth_generation == auth_generation
            for presence in self._repository.list_player_presence()
        ):
            return False
        state = self._require_room()
        now_ms = self._now_ms()
        expires_at_ms = (
            None
            if state.status in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}
            else now_ms + DISCONNECT_GRACE_MS
        )
        presence = PlayerPresenceRecord(
            player_id=player_id,
            auth_generation=auth_generation,
            disconnected_at_ms=now_ms,
            disconnect_expires_at_ms=expires_at_ms,
        )
        transition = None
        if state.status not in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
            if connected_identities is None:
                disconnected_ids = {
                    item.player_id
                    for item in self._repository.list_player_presence()
                }
                disconnected_ids.add(player_id)
                connected_player_ids = {
                    player.player_id
                    for player in state.players
                    if str(player.player_id) not in disconnected_ids
                }
            else:
                connected_player_ids = {
                    PlayerId(identity[0])
                    for identity in self._active_socket_identities(
                        connected_identities
                    )
                    if identity != (player_id, auth_generation)
                }
            transition = apply_lobby_disconnect(
                state,
                player_id,
                connected_player_ids,
                now_ms=now_ms,
            )
        if transition is None:
            return self._repository.set_player_disconnected(presence)
        self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(transition.state),
            events=self._transition_events(transition),
            upsert_player_presence=presence,
        )
        return True

    def next_presence_alarm_ms(self) -> int | None:
        """Return the earliest pending pre-match disconnect deadline."""

        return self._repository.next_presence_alarm_ms()

    def expire_disconnected_players(
        self,
        connected_identities: Sequence[tuple[str, int]],
    ) -> tuple[str, ...]:
        """Idempotently evict every due pre-match player that remains offline.

        Live WebSocket identities are reconciled before inspecting deadlines so
        an alarm delivered after hibernation cannot remove a connected player.
        Each eviction uses the normal leave transition, including readiness
        invalidation, host transfer, credential revocation, events, and revision.
        """

        connected = set(self._active_socket_identities(connected_identities))
        self.reconcile_socket_presence(tuple(sorted(connected)))

        state = self._require_room()
        if state.status in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
            self._repository.clear_presence_expiration_deadlines()
            return ()

        now_ms = self._now_ms()
        due = tuple(
            presence
            for presence in self._repository.list_player_presence()
            if presence.disconnect_expires_at_ms is not None
            and presence.disconnect_expires_at_ms <= now_ms
            and (presence.player_id, presence.auth_generation) not in connected
        )
        due = tuple(
            sorted(
                due,
                key=lambda presence: (
                    presence.disconnect_expires_at_ms or 0,
                    presence.player_id,
                ),
            )
        )
        expired: list[str] = []
        for presence in due:
            # A prior iteration can transfer host permission or finish the room,
            # so reconstruct canonical state before every normal transition.
            current = self._require_room()
            if current.status in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
                self._repository.clear_presence_expiration_deadlines()
                break
            active_presence = {
                (item.player_id, item.auth_generation): item
                for item in self._repository.list_player_presence()
            }.get((presence.player_id, presence.auth_generation))
            if (
                active_presence is None
                or active_presence.disconnect_expires_at_ms is None
                or active_presence.disconnect_expires_at_ms > now_ms
            ):
                continue
            try:
                transition = expire_disconnected_lobby_player(
                    current,
                    presence.player_id,
                    now_ms=now_ms,
                )
            except LobbyDomainError:
                # An at-least-once alarm may observe an already-applied removal.
                continue
            self._commit(
                transition.state,
                expected_revision=current.revision,
                players=self._player_records_for_state(transition.state),
                events=self._transition_events(transition),
            )
            expired.append(presence.player_id)
        return tuple(expired)

    def execute_command(
        self,
        player_token: str,
        command_id: str,
        expected_revision: int,
        action_id: str,
    ) -> CommandResult:
        player = self._authenticate(player_token)
        state = self._require_room()
        _require_non_negative_int(expected_revision, "expected_revision")
        _require_text(command_id, "command_id")
        _require_text(action_id, "action_id")
        fingerprint = _command_fingerprint(command_id, expected_revision, action_id)
        try:
            replay = self._repository.get_processed_command(
                player.player_id,
                command_id,
                request_fingerprint=fingerprint,
            )
        except ProcessedCommandConflictError as exc:
            raise RoomServiceError(
                "commandIdReused",
                409,
                "The command ID was already used for a different request.",
                current_revision=state.revision,
            ) from exc
        if replay is not None:
            return self._replay_result(replay, player_token)
        if expected_revision != state.revision:
            raise RoomServiceError(
                "revisionConflict",
                409,
                "The room revision is stale.",
                current_revision=state.revision,
            )
        try:
            action = resolve_lobby_action(
                state,
                player.player_id,
                action_id,
                viewer_connected=self._player_is_connected(player.player_id),
            )
            transition = apply_lobby_action(
                state, player.player_id, action, now_ms=self._now_ms()
            )
        except LobbyDomainError as exc:
            raise _lobby_service_error(exc, current_revision=state.revision) from exc

        invite_token: str | None = None
        credential: RoomCredentialRecord | None = None
        if transition.rotate_invite:
            current_credential = self._repository.load_room_credentials()
            if current_credential is None:
                raise RoomServiceError(
                    "invalidInviteToken", 403, "The invite is unavailable."
                )
            invite_token = _derive_rotated_invite(
                player_token, str(state.room_id), player.player_id, command_id
            )
            credential = RoomCredentialRecord(
                invite_token_hash=_capability_hash(invite_token),
                invite_generation=current_credential.invite_generation + 1,
                created_at_ms=current_credential.created_at_ms,
                updated_at_ms=transition.state.updated_at_ms,
            )

        if transition.session_ended:
            result: CommandResult = SessionEndedResult(
                revision=transition.state.revision
            )
        else:
            result = CommandViewResult(
                view=self._view(
                    transition.state,
                    player.player_id,
                    now_ms=transition.state.updated_at_ms,
                ),
                invite_token=invite_token,
            )
        command = ProcessedCommandRecord(
            player_id=player.player_id,
            command_id=command_id,
            request_fingerprint=fingerprint,
            revision=transition.state.revision,
            result_json=_stored_command_result(
                result, rotated_invite=transition.rotate_invite
            ),
            processed_at_ms=transition.state.updated_at_ms,
        )
        self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(transition.state),
            events=self._transition_events(transition),
            processed_commands=(command,),
            room_credentials=credential,
        )
        return result

    def update_config(
        self, player_token: str, expected_revision: int, config_json: str
    ) -> CommandViewResult:
        player = self._authenticate(player_token)
        state = self._require_room()
        try:
            authorize_lobby_config(state, player.player_id)
        except LobbyDomainError as exc:
            raise _lobby_service_error(exc, current_revision=state.revision) from exc
        _require_non_negative_int(expected_revision, "expected_revision")
        if expected_revision != state.revision:
            raise RoomServiceError(
                "revisionConflict",
                409,
                "The room revision is stale.",
                current_revision=state.revision,
            )
        config = _parse_complete_config(config_json)
        if config != GameConfig():
            raise RoomServiceError(
                "invalidConfig",
                422,
                "This ruleset does not support custom configuration.",
                current_revision=state.revision,
            )
        try:
            transition = update_lobby_config(
                state, player.player_id, config, now_ms=self._now_ms()
            )
        except LobbyDomainError as exc:
            raise _lobby_service_error(exc, current_revision=state.revision) from exc
        if config == state.config:
            return CommandViewResult(
                view=self._view(
                    state,
                    player.player_id,
                    now_ms=transition.state.updated_at_ms,
                )
            )
        persisted = self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(transition.state),
            events=self._transition_events(transition),
        )
        return CommandViewResult(
            view=self._view(
                persisted,
                player.player_id,
                now_ms=transition.state.updated_at_ms,
            )
        )

    def projected_events(
        self, player_token: str, after_sequence: int = 0
    ) -> ProjectedEvents:
        self._authenticate(player_token)
        _require_non_negative_int(after_sequence, "after_sequence")
        stored = self._repository.list_events(after_sequence=after_sequence)
        events = tuple(_project_event(event) for event in stored)
        return ProjectedEvents(
            events=events,
            next_sequence=events[-1].public_sequence if events else after_sequence,
        )

    def issue_socket_ticket(self, player_token: str) -> IssuedSocketTicket:
        player = self._authenticate(player_token)
        now_ms = self._now_ms()
        ticket = self._new_capability()
        record = SocketTicketRecord(
            ticket_hash=_capability_hash(ticket),
            player_id=player.player_id,
            auth_generation=player.auth_generation,
            expires_at_ms=now_ms + SOCKET_TICKET_TTL_MS,
            created_at_ms=now_ms,
        )
        self._repository.create_socket_ticket(record)
        return IssuedSocketTicket(ticket=ticket, expires_at_ms=record.expires_at_ms)

    def consume_socket_ticket(
        self, ticket: str, now_ms: int | None = None
    ) -> AuthenticatedPlayer:
        timestamp = self._now_ms() if now_ms is None else now_ms
        _require_non_negative_int(timestamp, "now_ms")
        try:
            record = self._repository.consume_socket_ticket(
                _capability_hash(ticket), consumed_at_ms=timestamp
            )
        except (SocketTicketUnavailableError, TypeError, ValueError) as exc:
            raise RoomServiceError(
                "invalidSocketTicket", 401, "The socket ticket is invalid."
            ) from exc
        return AuthenticatedPlayer(
            player_id=record.player_id,
            auth_generation=record.auth_generation,
        )

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
        player = self._repository.authenticate_player(
            _capability_hash(player_token)
        )
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
            player_id = _require_text(identity[0], "player_id")
            generation = _require_non_negative_int(
                identity[1], "auth_generation"
            )
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
        actual = _capability_hash(invite_token)
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
        player = next(value for value in state.players if str(value.player_id) == player_id)
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
            token_hash=_capability_hash(player_token),
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
                token_hash = _capability_hash(raw)
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
                details_json=_canonical_json(dict(details)),
            ),
            created_at_ms=state.updated_at_ms,
        )

    def _transition_events(
        self, transition: LobbyTransition
    ) -> tuple[ProjectedAuditEvent, ...]:
        values = ((transition.event_type, transition.event_details),) + transition.additional_events
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
            encoded = _canonical_json(result_value)
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
            invite = _derive_rotated_invite(
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
        return _require_text(self._id_source(prefix), f"{prefix}_id")

    def _now_ms(self) -> int:
        return _require_non_negative_int(self._clock.now_ms(), "clock.now_ms")


def _lobby_service_error(
    error: LobbyDomainError, *, current_revision: int | None = None
) -> RoomServiceError:
    mapping = {
        "INVALID_DISPLAY_NAME": (422, "invalidDisplayName", "The display name is invalid."),
        "DISPLAY_NAME_TAKEN": (409, "displayNameTaken", "The display name is already in use."),
        "ROOM_FULL": (409, "roomFull", "The room has no open seats."),
        "ROOM_CLOSED": (409, "roomClosed", "The room roster is frozen."),
        "HOST_REQUIRED": (403, "hostRequired", "Host permission is required."),
        "ACTION_NOT_AVAILABLE": (409, "actionNotAvailable", "The action is not available."),
        "PLAYER_NOT_FOUND": (401, "invalidPlayerToken", "Authentication is invalid."),
        "PLAYER_ID_TAKEN": (409, "playerIdTaken", "The player identity is already in use."),
    }
    status, code, message = mapping.get(
        error.code,
        (409, "roomConflict", "The room request conflicts with its current state."),
    )
    return RoomServiceError(
        code, status, message, current_revision=current_revision
    )


def _parse_complete_config(config_json: str) -> GameConfig:
    if not isinstance(config_json, str):
        raise RoomServiceError("invalidConfig", 422, "The configuration is invalid.")
    aliases = {field.alias or name for name, field in GameConfig.model_fields.items()}
    try:
        value = json.loads(config_json)
        if type(value) is not dict or set(value) != aliases:
            raise ValueError("configuration shape is incomplete")
        return GameConfig.model_validate_json(config_json, strict=True)
    except (TypeError, ValueError, ValidationError) as exc:
        raise RoomServiceError(
            "invalidConfig", 422, "The configuration is invalid."
        ) from exc


def _project_event(event: StoredAuditEvent) -> ProjectedRoomEvent:
    payload = event.payload
    if isinstance(payload, LobbyAuditPayload):
        details = payload.details
    elif isinstance(payload, RoomInitializedAuditPayload):
        details = {}
    elif isinstance(payload, RoomStateCommittedAuditPayload):
        details = {"previousRevision": payload.previous_revision}
    else:  # pragma: no cover
        raise RuntimeError("unsupported stored audit event")
    return ProjectedRoomEvent(
        public_sequence=event.public_sequence,
        revision=event.revision,
        type=event.event_type,
        payload=details,
        created_at_ms=event.created_at_ms,
    )


def _stored_command_result(result: CommandResult, *, rotated_invite: bool) -> str:
    result_data = result.canonical_data()
    result_data.pop("inviteToken", None)
    return _canonical_json({"result": result_data, "rotatedInvite": rotated_invite})


def _command_fingerprint(
    command_id: str, expected_revision: int, action_id: str
) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "actionId": action_id,
                "commandId": command_id,
                "expectedRevision": expected_revision,
            }
        ).encode()
    ).hexdigest()


def _derive_rotated_invite(
    player_token: str, room_id: str, player_id: str, command_id: str
) -> str:
    material = b"\x00".join(
        value.encode("utf-8") for value in (room_id, player_id, command_id)
    )
    digest = hmac.new(
        player_token.encode("utf-8"),
        _INVITE_ROTATION_DOMAIN + material,
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _capability_hash(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("capability must be a string")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _require_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


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
    "RoomOrchestrator",
    "RoomServiceError",
    "SOCKET_TICKET_TTL_MS",
    "SessionEndedResult",
]
