"""Room creation, lobby commands, event projection, and socket tickets."""

from __future__ import annotations

if __package__.startswith("app."):
    from ..game import GameConfig, PublicRoomView
    from ..lobby import (
        LobbyDomainError,
        apply_lobby_action,
        authorize_lobby_config,
        create_lobby_room,
        join_lobby_room,
        resolve_lobby_action,
        update_lobby_config,
    )
    from ..persistence import (
        ProcessedCommandConflictError,
        ProcessedCommandRecord,
        RoomAlreadyExistsError,
        RoomCredentialRecord,
        SocketTicketRecord,
        SocketTicketUnavailableError,
    )
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import GameConfig, PublicRoomView
    from lobby import (
        LobbyDomainError,
        apply_lobby_action,
        authorize_lobby_config,
        create_lobby_room,
        join_lobby_room,
        resolve_lobby_action,
        update_lobby_config,
    )
    from persistence import (
        ProcessedCommandConflictError,
        ProcessedCommandRecord,
        RoomAlreadyExistsError,
        RoomCredentialRecord,
        SocketTicketRecord,
        SocketTicketUnavailableError,
    )

from .codec import (
    capability_hash,
    command_fingerprint,
    derive_rotated_invite,
    lobby_service_error,
    parse_complete_config,
    project_event,
    require_non_negative_int,
    require_text,
    stored_command_result,
)
from .contracts import (
    AuthenticatedPlayer,
    CommandResult,
    CommandViewResult,
    IssuedSocketTicket,
    PlayerSession,
    ProjectedEvents,
    RoomCreation,
    RoomServiceError,
    SOCKET_TICKET_TTL_MS,
    SessionEndedResult,
)


class RoomCommands:
    """Command-side use cases layered on a :class:`RoomKernel`."""

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
                invite_token_hash=capability_hash(invite_token),
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
                player_presence=(self._initial_presence(player_id, now_ms=now_ms),),
                room_credentials=credential,
            )
        except LobbyDomainError as exc:
            raise lobby_service_error(exc) from exc
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
            raise lobby_service_error(exc, current_revision=state.revision) from exc
        persisted = self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(
                transition.state, new_tokens={player_id: player_token}
            ),
            events=self._transition_events(transition),
            player_presence=(self._initial_presence(player_id, now_ms=now_ms),),
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

    def execute_command(
        self,
        player_token: str,
        command_id: str,
        expected_revision: int,
        action_id: str,
    ) -> CommandResult:
        player = self._authenticate(player_token)
        state = self._require_room()
        require_non_negative_int(expected_revision, "expected_revision")
        require_text(command_id, "command_id")
        require_text(action_id, "action_id")
        fingerprint = command_fingerprint(
            command_id, expected_revision, action_id
        )
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
            raise lobby_service_error(exc, current_revision=state.revision) from exc

        invite_token: str | None = None
        credential: RoomCredentialRecord | None = None
        if transition.rotate_invite:
            current_credential = self._repository.load_room_credentials()
            if current_credential is None:
                raise RoomServiceError(
                    "invalidInviteToken", 403, "The invite is unavailable."
                )
            invite_token = derive_rotated_invite(
                player_token, str(state.room_id), player.player_id, command_id
            )
            credential = RoomCredentialRecord(
                invite_token_hash=capability_hash(invite_token),
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
            result_json=stored_command_result(
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
            raise lobby_service_error(exc, current_revision=state.revision) from exc
        require_non_negative_int(expected_revision, "expected_revision")
        if expected_revision != state.revision:
            raise RoomServiceError(
                "revisionConflict",
                409,
                "The room revision is stale.",
                current_revision=state.revision,
            )
        config = parse_complete_config(config_json)
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
            raise lobby_service_error(exc, current_revision=state.revision) from exc
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
        require_non_negative_int(after_sequence, "after_sequence")
        stored = self._repository.list_events(after_sequence=after_sequence)
        events = tuple(project_event(event) for event in stored)
        return ProjectedEvents(
            events=events,
            next_sequence=events[-1].public_sequence if events else after_sequence,
        )

    def issue_socket_ticket(self, player_token: str) -> IssuedSocketTicket:
        player = self._authenticate(player_token)
        now_ms = self._now_ms()
        ticket = self._new_capability()
        record = SocketTicketRecord(
            ticket_hash=capability_hash(ticket),
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
        require_non_negative_int(timestamp, "now_ms")
        try:
            record = self._repository.consume_socket_ticket(
                capability_hash(ticket), consumed_at_ms=timestamp
            )
        except (SocketTicketUnavailableError, TypeError, ValueError) as exc:
            raise RoomServiceError(
                "invalidSocketTicket", 401, "The socket ticket is invalid."
            ) from exc
        return AuthenticatedPlayer(
            player_id=record.player_id,
            auth_generation=record.auth_generation,
        )


__all__ = ["RoomCommands"]
