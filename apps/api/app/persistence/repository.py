"""Durable, platform-neutral storage for a single Mahjong room.

``room_state`` is the only reconstruction source.  The other tables are
deliberate projections used for authentication, safe audit history,
idempotency, and short-lived socket tickets.  This module only depends on a
small synchronous SQL protocol so the same repository can run against a
SQLite-backed Durable Object or CPython's ``sqlite3`` module.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

if __package__ == "persistence":  # Python Workers load from the app directory.
    from game import RoomState
else:
    from ..game import RoomState

from .errors import (
    CorruptRoomStateError,
    PersistenceError,
    PlayerProjectionError,
    ProcessedCommandConflictError,
    RevisionConflictError,
    RoomAlreadyExistsError,
    RoomNotFoundError,
    SocketTicketUnavailableError,
    UnsupportedSchemaVersionError,
)
from .records import (
    LobbyAuditPayload,
    PlayerPresenceRecord,
    PlayerRecord,
    ProcessedCommandRecord,
    ProjectedAuditEvent,
    RoomCredentialRecord,
    RoomInitializedAuditPayload,
    RoomStateCommittedAuditPayload,
    RoomStateRecord,
    SafeAuditPayload,
    SocketTicketRecord,
    StoredAuditEvent,
    _canonicalize_json_text,
    _identity_text,
    _now_ms,
    _parse_audit_payload,
    _player_presence_from_row,
    _player_record_from_row,
    _require_non_negative_int,
    _require_sha256_hex,
    _require_text,
    _validate_event,
    _validate_player,
    _validate_player_presence,
    _validate_processed_command,
    _validate_room_credential,
    _validate_socket_ticket,
)
from .schema import (
    application_table_names as _application_table_names,
    initialize_schema as _initialize_schema,
    upgrade_room_snapshots_to_v2 as _upgrade_room_snapshots_to_v2,
)
from .sql import (
    CloudflareSqlExecutor,
    SQLiteSqlExecutor,
    SqliteSqlExecutor,
    SynchronousSqlExecutor,
    one as _one,
    row_value as _row_value,
    rows as _rows,
    rows_written as _rows_written,
)
from .validation import (
    _external_roster_signature,
    _merge_player_lifecycle,
    _normalize_player_identities,
    _record_from_row,
    _record_from_state,
    _validate_audit_events,
    _validate_connected_presence_references,
    _validate_players_against_state,
    _validate_presence_references,
    _validate_room_credential_transition,
    _validate_security_references,
    _validate_stored_event_history,
)


_ROOM_STATE_SINGLETON_ID = 1


class RoomRepository:
    """Synchronous repository for one room per SQL database."""

    def __init__(self, executor: SynchronousSqlExecutor) -> None:
        self._executor = executor

    @classmethod
    def from_durable_storage(cls, storage: Any) -> "RoomRepository":
        return cls(CloudflareSqlExecutor(storage))

    @classmethod
    def from_sqlite(cls, connection: Any) -> "RoomRepository":
        return cls(SQLiteSqlExecutor(connection))

    def initialize_schema(self, *, applied_at_ms: int | None = None) -> None:
        """Apply all application SQL migrations exactly once."""

        _initialize_schema(self._executor, applied_at_ms=applied_at_ms)

    def _upgrade_room_snapshots_to_v2(self) -> None:
        """Rewrite v1 room JSON canonically while preserving history."""

        _upgrade_room_snapshots_to_v2(self._executor)

    def _application_table_names(self) -> set[str]:
        return _application_table_names(self._executor)

    def create_room(
        self,
        state: RoomState,
        *,
        players: Sequence[PlayerRecord] = (),
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        socket_tickets: Sequence[SocketTicketRecord] = (),
        player_presence: Sequence[PlayerPresenceRecord] = (),
        room_credentials: RoomCredentialRecord | None = None,
    ) -> RoomState:
        """Create the canonical room and its supplied projections atomically."""

        record = _record_from_state(state)
        state = record.state
        player_records = tuple(players)
        audit_events = tuple(events)
        command_records = tuple(processed_commands)
        ticket_records = tuple(socket_tickets)
        presence_records = tuple(player_presence)
        if room_credentials is not None:
            _validate_room_credential(room_credentials)
        _validate_players_against_state(
            player_records, state, allow_historical=False
        )
        _validate_audit_events(audit_events, record)
        _validate_security_references(
            command_records,
            ticket_records,
            player_records,
            allowed_command_player_ids={
                player.player_id
                for player in player_records
                if player.left_at_ms is None
            },
        )
        _validate_presence_references(presence_records, player_records)

        def create() -> None:
            if self._room_row() is not None:
                raise RoomAlreadyExistsError("room state is already initialized")
            self._insert_room_record(record)
            if room_credentials is not None:
                self._insert_room_credential(room_credentials)
            self._replace_players(player_records)
            self._insert_player_presence(presence_records)
            self._append_events(
                audit_events,
                revision=record.revision,
                room_id=record.room_id,
            )
            self._insert_processed_commands(
                command_records, committed_revision=record.revision
            )
            self._insert_socket_tickets(ticket_records)

        self._executor.transaction(create)
        return record.state

    def load_room(self) -> RoomState | None:
        """Reconstruct the room from ``room_state`` and no auxiliary table."""

        record = self.load_room_record()
        return None if record is None else record.state

    def load_room_record(self) -> RoomStateRecord | None:
        row = self._room_row()
        if row is None:
            return None
        return _record_from_row(row)

    def compare_and_swap(
        self,
        expected_revision: int,
        state: RoomState,
        *,
        players: Sequence[PlayerRecord] | None = None,
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        socket_tickets: Sequence[SocketTicketRecord] = (),
        player_presence: Sequence[PlayerPresenceRecord] = (),
        upsert_player_presence: PlayerPresenceRecord | None = None,
        clear_player_presence: Sequence[tuple[str, int]] = (),
        room_credentials: RoomCredentialRecord | None = None,
    ) -> RoomState:
        """Commit the next room revision and all projections in one transaction."""

        _require_non_negative_int(expected_revision, "expected_revision")
        record = _record_from_state(state)
        state = record.state
        player_records = None if players is None else tuple(players)
        audit_events = tuple(events)
        command_records = tuple(processed_commands)
        ticket_records = tuple(socket_tickets)
        presence_records = tuple(player_presence)
        presence_upsert = upsert_player_presence
        if (
            presence_upsert is not None
            and type(presence_upsert) is not PlayerPresenceRecord
        ):
            raise TypeError("upsert_player_presence must be an exact PlayerPresenceRecord")
        clear_presence = _normalize_player_identities(clear_player_presence)
        if (
            presence_upsert is not None
            and (presence_upsert.player_id, presence_upsert.auth_generation)
            in clear_presence
        ):
            raise ValueError("the same player presence cannot be upserted and cleared")
        if room_credentials is not None:
            _validate_room_credential(room_credentials)
        if record.revision != expected_revision + 1:
            raise ValueError(
                "committed RoomState revision must equal expected_revision + 1"
            )
        _validate_audit_events(audit_events, record)

        def commit() -> None:
            current_row = self._room_row()
            if current_row is None:
                raise RoomNotFoundError("room state has not been initialized")
            current = _record_from_row(current_row)
            if current.revision != expected_revision:
                raise RevisionConflictError(expected_revision, current.revision)

            immutable_fields = (
                "room_id",
                "ruleset_id",
                "ruleset_version",
                "state_schema_version",
                "created_at_ms",
            )
            changed_fields = [
                field
                for field in immutable_fields
                if getattr(current, field) != getattr(record, field)
            ]
            if changed_fields:
                raise ValueError(
                    "immutable room metadata cannot change: "
                    + ", ".join(changed_fields)
                )
            if record.updated_at_ms < current.updated_at_ms:
                raise ValueError("updated_at_ms cannot move backwards across commits")

            existing_players = self._load_players()
            _validate_players_against_state(
                existing_players,
                current.state,
                allow_historical=True,
            )
            if player_records is None:
                if _external_roster_signature(current.state) != (
                    _external_roster_signature(state)
                ):
                    raise PlayerProjectionError(
                        "roster changes require a complete players projection"
                    )
                effective_players = existing_players
                _validate_players_against_state(
                    effective_players, state, allow_historical=True
                )
            else:
                effective_players = _merge_player_lifecycle(
                    existing_players,
                    player_records,
                    state,
                    revocation_at_ms=record.updated_at_ms,
                )

            _validate_security_references(
                command_records,
                ticket_records,
                effective_players,
                allowed_command_player_ids={
                    player.player_id
                    for player in existing_players
                    if player.left_at_ms is None
                },
            )
            _validate_presence_references(presence_records, effective_players)
            _validate_presence_references(
                () if presence_upsert is None else (presence_upsert,),
                effective_players,
            )
            _validate_connected_presence_references(
                clear_presence,
                effective_players,
            )

            if room_credentials is not None:
                current_credentials = self.load_room_credentials()
                if current_credentials is None:
                    raise PlayerProjectionError(
                        "room invite credentials have not been initialized"
                    )
                _validate_room_credential_transition(
                    current_credentials, room_credentials
                )

            cursor = self._executor.exec(
                """
                UPDATE room_state
                SET snapshot_json = ?,
                    ruleset_id = ?,
                    ruleset_version = ?,
                    state_schema_version = ?,
                    revision = ?,
                    config_json = ?,
                    created_at_ms = ?,
                    updated_at_ms = ?
                WHERE singleton_id = ? AND revision = ?
                """,
                record.snapshot_json,
                record.ruleset_id,
                record.ruleset_version,
                record.state_schema_version,
                record.revision,
                record.config_json,
                record.created_at_ms,
                record.updated_at_ms,
                _ROOM_STATE_SINGLETON_ID,
                expected_revision,
            )
            rows_written = _rows_written(cursor)
            if rows_written is not None and rows_written != 1:
                raise RevisionConflictError(expected_revision, current.revision)

            if player_records is not None:
                self._replace_players(effective_players)
            self._insert_player_presence(presence_records)
            self._apply_player_presence_mutation(
                upsert=presence_upsert,
                clear_identities=clear_presence,
            )
            if getattr(state.status, "value", state.status) in {
                "IN_MATCH",
                "FINISHED",
            }:
                pending = _rows(
                    self._executor.exec(
                        """
                        SELECT player_id FROM player_presence
                        WHERE disconnect_expires_at_ms IS NOT NULL
                        """
                    )
                )
                if pending:
                    self._executor.exec(
                        """
                        UPDATE player_presence
                        SET disconnect_expires_at_ms = NULL
                        WHERE disconnect_expires_at_ms IS NOT NULL
                        """
                    )
                    self._advance_presence_version()
            if room_credentials is not None:
                self._replace_room_credential(room_credentials)
            self._append_events(
                audit_events,
                revision=record.revision,
                room_id=record.room_id,
            )
            self._insert_processed_commands(
                command_records, committed_revision=record.revision
            )
            self._insert_socket_tickets(ticket_records)

        self._executor.transaction(commit)
        return record.state

    def commit(
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
        """Keyword-oriented alias for :meth:`compare_and_swap`."""

        return self.compare_and_swap(
            expected_revision,
            state,
            players=players,
            events=events,
            processed_commands=processed_commands,
            socket_tickets=socket_tickets,
            player_presence=player_presence,
            upsert_player_presence=upsert_player_presence,
            clear_player_presence=clear_player_presence,
            room_credentials=room_credentials,
        )

    def load_room_credentials(self) -> RoomCredentialRecord | None:
        rows = _rows(
            self._executor.exec(
                """
                SELECT invite_token_hash, invite_generation,
                       created_at_ms, updated_at_ms
                FROM room_credentials
                WHERE singleton_id = ?
                """,
                _ROOM_STATE_SINGLETON_ID,
            )
        )
        if len(rows) > 1:
            raise CorruptRoomStateError("multiple room credential rows found")
        if not rows:
            return None
        row = rows[0]
        try:
            return RoomCredentialRecord(
                invite_token_hash=str(_row_value(row, "invite_token_hash")),
                invite_generation=int(_row_value(row, "invite_generation")),
                created_at_ms=int(_row_value(row, "created_at_ms")),
                updated_at_ms=int(_row_value(row, "updated_at_ms")),
            )
        except (TypeError, ValueError) as exc:
            raise CorruptRoomStateError("stored room credentials are invalid") from exc

    def get_player(
        self, player_id: str, *, include_revoked: bool = False
    ) -> PlayerRecord | None:
        player_id = _identity_text(player_id, "player_id")
        records = self._load_players()
        return next(
            (
                player
                for player in records
                if player.player_id == player_id
                and (include_revoked or player.left_at_ms is None)
            ),
            None,
        )

    def get_player_by_token_hash(self, token_hash: str) -> PlayerRecord | None:
        _require_sha256_hex(token_hash, "token_hash")
        rows = _rows(
            self._executor.exec(
                """
                SELECT player_id, seat_id, display_name, role, controller_json,
                       token_hash, auth_generation, joined_at_ms, updated_at_ms,
                       left_at_ms
                FROM players
                WHERE token_hash = ? AND left_at_ms IS NULL
                """,
                token_hash,
            )
        )
        if len(rows) > 1:
            raise CorruptRoomStateError("player token hash is not unique")
        return None if not rows else _player_record_from_row(rows[0])

    def authenticate_player(self, token_hash: str) -> PlayerRecord | None:
        """Atomically authenticate an active token against canonical membership."""

        _require_sha256_hex(token_hash, "token_hash")

        def authenticate() -> PlayerRecord | None:
            player = self.get_player_by_token_hash(token_hash)
            if player is None:
                return None
            state = self.load_room()
            if state is None:
                raise CorruptRoomStateError(
                    "active player credentials exist without canonical room state"
                )
            _validate_players_against_state(
                self._load_players(), state, allow_historical=True
            )
            return player

        return self._executor.transaction(authenticate)

    def list_player_records(
        self, *, include_revoked: bool = True
    ) -> tuple[PlayerRecord, ...]:
        records = self._load_players()
        if include_revoked:
            return records
        return tuple(player for player in records if player.left_at_ms is None)

    def set_player_disconnected(self, presence: PlayerPresenceRecord) -> bool:
        """Persist disconnected state for an active authentication generation.

        The operation is revision-neutral and returns whether the public
        presence projection changed.  Stale close notifications are ignored.
        """

        if type(presence) is not PlayerPresenceRecord:
            raise TypeError("presence must be an exact PlayerPresenceRecord")

        def update() -> bool:
            player = self.get_player(presence.player_id)
            if (
                player is None
                or player.auth_generation != presence.auth_generation
            ):
                return False
            return self._apply_player_presence_mutation(
                upsert=presence,
                clear_identities=(),
            )

        return self._executor.transaction(update)

    def set_player_connected(self, player_id: str, auth_generation: int) -> bool:
        """Clear durable disconnected state for an active socket identity."""

        return self.set_players_connected(((player_id, auth_generation),))

    def set_players_connected(
        self, identities: Sequence[tuple[str, int]]
    ) -> bool:
        """Atomically clear disconnected state for active socket identities."""

        normalized = _normalize_player_identities(identities)
        if not normalized:
            return False

        def update() -> bool:
            active = {
                (player.player_id, player.auth_generation)
                for player in self.list_player_records(include_revoked=False)
            }
            confirmed = tuple(
                identity for identity in normalized if identity in active
            )
            return self._apply_player_presence_mutation(
                upsert=None,
                clear_identities=confirmed,
            )

        return self._executor.transaction(update)

    def list_player_presence(self) -> tuple[PlayerPresenceRecord, ...]:
        """Return disconnected state for active players and generations only."""

        rows = _rows(
            self._executor.exec(
                """
                SELECT presence.player_id AS player_id,
                       presence.auth_generation AS auth_generation,
                       presence.disconnected_at_ms AS disconnected_at_ms,
                       presence.disconnect_expires_at_ms AS disconnect_expires_at_ms
                FROM player_presence AS presence
                JOIN players AS player ON player.player_id = presence.player_id
                WHERE player.left_at_ms IS NULL
                  AND player.auth_generation = presence.auth_generation
                ORDER BY presence.player_id
                """
            )
        )
        try:
            return tuple(_player_presence_from_row(row) for row in rows)
        except (TypeError, ValueError) as exc:
            raise CorruptRoomStateError("stored player presence is invalid") from exc

    def next_presence_alarm_ms(self) -> int | None:
        rows = _rows(
            self._executor.exec(
                """
                SELECT MIN(presence.disconnect_expires_at_ms) AS deadline
                FROM player_presence AS presence
                JOIN players AS player ON player.player_id = presence.player_id
                WHERE player.left_at_ms IS NULL
                  AND player.auth_generation = presence.auth_generation
                  AND presence.disconnect_expires_at_ms IS NOT NULL
                """
            )
        )
        if len(rows) != 1:
            raise CorruptRoomStateError("presence alarm query returned invalid rows")
        deadline = _row_value(rows[0], "deadline")
        return None if deadline is None else int(deadline)

    def presence_version(self) -> int:
        rows = _rows(
            self._executor.exec(
                """
                SELECT presence_version
                FROM room_presence
                WHERE singleton_id = ?
                """,
                _ROOM_STATE_SINGLETON_ID,
            )
        )
        if len(rows) != 1:
            raise CorruptRoomStateError("room presence metadata is unavailable")
        return _require_non_negative_int(
            int(_row_value(rows[0], "presence_version")),
            "presence_version",
        )

    def clear_presence_expiration_deadlines(self) -> bool:
        """Freeze disconnected seats, retaining their disconnected projection."""

        def update() -> bool:
            rows = _rows(
                self._executor.exec(
                    """
                    SELECT presence.player_id AS player_id
                    FROM player_presence AS presence
                    JOIN players AS player ON player.player_id = presence.player_id
                    WHERE player.left_at_ms IS NULL
                      AND player.auth_generation = presence.auth_generation
                      AND presence.disconnect_expires_at_ms IS NOT NULL
                    """
                )
            )
            if not rows:
                return False
            self._executor.exec(
                """
                UPDATE player_presence
                SET disconnect_expires_at_ms = NULL
                WHERE player_id IN (
                    SELECT presence.player_id
                    FROM player_presence AS presence
                    JOIN players AS player
                      ON player.player_id = presence.player_id
                    WHERE player.left_at_ms IS NULL
                      AND player.auth_generation = presence.auth_generation
                )
                """
            )
            self._advance_presence_version()
            return True

        return self._executor.transaction(update)

    def _advance_presence_version(self) -> int:
        rows = _rows(
            self._executor.exec(
                """
                UPDATE room_presence
                SET presence_version = presence_version + 1
                WHERE singleton_id = ?
                RETURNING presence_version
                """,
                _ROOM_STATE_SINGLETON_ID,
            )
        )
        if len(rows) != 1:
            raise CorruptRoomStateError("room presence metadata is unavailable")
        return int(_row_value(rows[0], "presence_version"))

    def get_processed_command(
        self,
        player_id: str,
        command_id: str,
        *,
        request_fingerprint: str | None = None,
    ) -> ProcessedCommandRecord | None:
        """Return a prior result, rejecting command-id reuse with new content."""

        player_id = _identity_text(player_id, "player_id")
        command_id = _identity_text(command_id, "command_id")
        result = _rows(
            self._executor.exec(
                """
                SELECT command.player_id AS player_id,
                       command.command_id AS command_id,
                       command.request_fingerprint AS request_fingerprint,
                       command.revision AS revision,
                       command.result_json AS result_json,
                       command.processed_at_ms AS processed_at_ms
                FROM processed_commands AS command
                JOIN players AS player ON player.player_id = command.player_id
                WHERE command.player_id = ? AND command.command_id = ?
                  AND player.left_at_ms IS NULL
                """,
                player_id,
                command_id,
            )
        )
        if not result:
            return None
        row = result[0]
        record = ProcessedCommandRecord(
            player_id=str(_row_value(row, "player_id")),
            command_id=str(_row_value(row, "command_id")),
            request_fingerprint=str(_row_value(row, "request_fingerprint")),
            revision=int(_row_value(row, "revision")),
            result_json=str(_row_value(row, "result_json")),
            processed_at_ms=int(_row_value(row, "processed_at_ms")),
        )
        if (
            request_fingerprint is not None
            and record.request_fingerprint != request_fingerprint
        ):
            raise ProcessedCommandConflictError(
                "command id was already used with a different request fingerprint"
            )
        return record

    # The name describes the intended call-site behavior: check before transition.
    reuse_processed_command = get_processed_command

    def list_events(self, *, after_sequence: int = 0) -> tuple[StoredAuditEvent, ...]:
        _require_non_negative_int(after_sequence, "after_sequence")
        canonical = self.load_room_record()
        all_rows = _rows(
            self._executor.exec(
                """
                SELECT public_sequence, revision, event_type, event_json, created_at_ms
                FROM events
                ORDER BY public_sequence
                """
            )
        )
        sequences = [int(_row_value(row, "public_sequence")) for row in all_rows]
        if sequences != list(range(1, len(sequences) + 1)):
            raise CorruptRoomStateError("public audit event sequence is not contiguous")
        all_events: list[StoredAuditEvent] = []
        for row in all_rows:
            sequence = int(_row_value(row, "public_sequence"))
            event_type = str(_row_value(row, "event_type"))
            event_json = str(_row_value(row, "event_json"))
            revision = int(_row_value(row, "revision"))
            payload = _parse_audit_payload(event_type, event_json)
            if payload.revision != revision:
                raise CorruptRoomStateError(
                    "audit payload revision does not match its indexed revision"
                )
            all_events.append(
                StoredAuditEvent(
                    payload=payload,
                    created_at_ms=int(_row_value(row, "created_at_ms")),
                    public_sequence=sequence,
                    revision=revision,
                )
            )
        _validate_stored_event_history(all_events, canonical)
        return tuple(
            event for event in all_events if event.public_sequence > after_sequence
        )

    def get_socket_ticket(self, ticket_hash: str) -> SocketTicketRecord | None:
        _require_sha256_hex(ticket_hash, "ticket_hash")
        rows = _rows(
            self._executor.exec(
                """
                SELECT ticket.ticket_hash AS ticket_hash,
                       ticket.player_id AS player_id,
                       ticket.auth_generation AS auth_generation,
                       ticket.expires_at_ms AS expires_at_ms,
                       ticket.created_at_ms AS created_at_ms,
                       ticket.consumed_at_ms AS consumed_at_ms
                FROM socket_tickets AS ticket
                JOIN players AS player ON player.player_id = ticket.player_id
                WHERE ticket.ticket_hash = ?
                  AND player.left_at_ms IS NULL
                  AND player.auth_generation = ticket.auth_generation
                """,
                ticket_hash,
            )
        )
        if not rows:
            return None
        row = rows[0]
        consumed = _row_value(row, "consumed_at_ms")
        return SocketTicketRecord(
            ticket_hash=str(_row_value(row, "ticket_hash")),
            player_id=str(_row_value(row, "player_id")),
            auth_generation=int(_row_value(row, "auth_generation")),
            expires_at_ms=int(_row_value(row, "expires_at_ms")),
            created_at_ms=int(_row_value(row, "created_at_ms")),
            consumed_at_ms=None if consumed is None else int(consumed),
        )

    def create_socket_ticket(self, ticket: SocketTicketRecord) -> SocketTicketRecord:
        """Issue a ticket atomically without changing the canonical revision."""

        if type(ticket) is not SocketTicketRecord:
            raise TypeError("ticket must be an exact SocketTicketRecord")

        def create() -> None:
            self._delete_unavailable_socket_tickets(ticket.created_at_ms)
            player = self.get_player(ticket.player_id)
            if player is None or player.auth_generation != ticket.auth_generation:
                raise PlayerProjectionError(
                    "socket ticket must reference the active auth generation"
                )
            self._insert_socket_tickets((ticket,))

        self._executor.transaction(create)
        return ticket

    def consume_socket_ticket(
        self, ticket_hash: str, *, consumed_at_ms: int
    ) -> SocketTicketRecord:
        """Atomically consume an unexpired ticket for an active auth generation."""

        _require_sha256_hex(ticket_hash, "ticket_hash")
        _require_non_negative_int(consumed_at_ms, "consumed_at_ms")

        def consume() -> SocketTicketRecord:
            self._delete_unavailable_socket_tickets(consumed_at_ms)
            rows = _rows(
                self._executor.exec(
                """
                UPDATE socket_tickets
                SET consumed_at_ms = ?
                WHERE ticket_hash = ?
                  AND consumed_at_ms IS NULL
                  AND expires_at_ms > ?
                  AND created_at_ms <= ?
                  AND (player_id, auth_generation) IN (
                      SELECT player_id, auth_generation FROM players
                      WHERE left_at_ms IS NULL
                  )
                RETURNING ticket_hash, player_id, auth_generation,
                          expires_at_ms, created_at_ms, consumed_at_ms
                """,
                consumed_at_ms,
                ticket_hash,
                consumed_at_ms,
                consumed_at_ms,
                )
            )
            if len(rows) != 1:
                raise SocketTicketUnavailableError("socket ticket is unavailable")
            row = rows[0]
            consumed = _row_value(row, "consumed_at_ms")
            return SocketTicketRecord(
                ticket_hash=str(_row_value(row, "ticket_hash")),
                player_id=str(_row_value(row, "player_id")),
                auth_generation=int(_row_value(row, "auth_generation")),
                expires_at_ms=int(_row_value(row, "expires_at_ms")),
                created_at_ms=int(_row_value(row, "created_at_ms")),
                consumed_at_ms=None if consumed is None else int(consumed),
            )

        return self._executor.transaction(consume)

    def cleanup_socket_tickets(self, *, now_ms: int) -> int:
        """Delete expired and consumed ticket rows without advancing revision."""

        _require_non_negative_int(now_ms, "now_ms")
        return self._executor.transaction(
            lambda: self._delete_unavailable_socket_tickets(now_ms)
        )

    def _delete_unavailable_socket_tickets(self, now_ms: int) -> int:
        cursor = self._executor.exec(
            """
            DELETE FROM socket_tickets
            WHERE consumed_at_ms IS NOT NULL OR expires_at_ms <= ?
            """,
            now_ms,
        )
        return _rows_written(cursor) or 0

    def _room_row(self) -> Any | None:
        rows = _rows(
            self._executor.exec(
                """
                SELECT singleton_id, room_id, snapshot_json, ruleset_id,
                       ruleset_version, state_schema_version, revision, config_json,
                       created_at_ms, updated_at_ms
                FROM room_state
                WHERE singleton_id = ?
                """,
                _ROOM_STATE_SINGLETON_ID,
            )
        )
        if len(rows) > 1:
            raise CorruptRoomStateError("multiple canonical room rows found")
        return None if not rows else rows[0]

    def _insert_room_record(self, record: RoomStateRecord) -> None:
        self._executor.exec(
            """
            INSERT INTO room_state (
                singleton_id, room_id, snapshot_json, ruleset_id, ruleset_version,
                state_schema_version, revision, config_json,
                created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _ROOM_STATE_SINGLETON_ID,
            record.room_id,
            record.snapshot_json,
            record.ruleset_id,
            record.ruleset_version,
            record.state_schema_version,
            record.revision,
            record.config_json,
            record.created_at_ms,
            record.updated_at_ms,
        )

    def _insert_room_credential(self, record: RoomCredentialRecord) -> None:
        _validate_room_credential(record)
        self._executor.exec(
            """
            INSERT INTO room_credentials (
                singleton_id, invite_token_hash, invite_generation,
                created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?)
            """,
            _ROOM_STATE_SINGLETON_ID,
            record.invite_token_hash,
            record.invite_generation,
            record.created_at_ms,
            record.updated_at_ms,
        )

    def _replace_room_credential(self, record: RoomCredentialRecord) -> None:
        cursor = self._executor.exec(
            """
            UPDATE room_credentials
            SET invite_token_hash = ?, invite_generation = ?,
                created_at_ms = ?, updated_at_ms = ?
            WHERE singleton_id = ?
            """,
            record.invite_token_hash,
            record.invite_generation,
            record.created_at_ms,
            record.updated_at_ms,
            _ROOM_STATE_SINGLETON_ID,
        )
        rows_written = _rows_written(cursor)
        if rows_written is not None and rows_written != 1:
            raise CorruptRoomStateError("room credentials disappeared during commit")

    def _replace_players(self, players: Sequence[PlayerRecord]) -> None:
        self._executor.exec("DELETE FROM players")
        seen_ids: set[str] = set()
        for player in players:
            _validate_player(player)
            if player.player_id in seen_ids:
                raise ValueError(f"duplicate player projection: {player.player_id!r}")
            seen_ids.add(player.player_id)
            self._executor.exec(
                """
                INSERT INTO players (
                    player_id, seat_id, display_name, role, controller_json,
                    token_hash, auth_generation, joined_at_ms, updated_at_ms, left_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                player.player_id,
                player.seat_id,
                player.display_name,
                player.role,
                _canonicalize_json_text(player.controller_json, "controller_json"),
                player.token_hash,
                player.auth_generation,
                player.joined_at_ms,
                player.updated_at_ms,
                player.left_at_ms,
            )
        stale_presence = _rows(
            self._executor.exec(
                """
                SELECT player_presence.player_id AS player_id
                FROM player_presence
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM players
                    WHERE players.player_id = player_presence.player_id
                      AND players.left_at_ms IS NULL
                      AND players.auth_generation = player_presence.auth_generation
                )
                """
            )
        )
        if stale_presence:
            self._executor.exec(
                """
                DELETE FROM player_presence
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM players
                    WHERE players.player_id = player_presence.player_id
                      AND players.left_at_ms IS NULL
                      AND players.auth_generation = player_presence.auth_generation
                )
                """
            )
            self._advance_presence_version()

    def _load_players(self) -> tuple[PlayerRecord, ...]:
        rows = _rows(
            self._executor.exec(
                """
                SELECT player_id, seat_id, display_name, role, controller_json,
                       token_hash, auth_generation, joined_at_ms, updated_at_ms,
                       left_at_ms
                FROM players
                ORDER BY player_id
                """
            )
        )
        records: list[PlayerRecord] = []
        try:
            for row in rows:
                records.append(_player_record_from_row(row))
        except (TypeError, ValueError) as exc:
            raise CorruptRoomStateError("stored player projection is invalid") from exc
        return tuple(records)

    def _append_events(
        self,
        events: Sequence[ProjectedAuditEvent],
        *,
        revision: int,
        room_id: str,
    ) -> tuple[StoredAuditEvent, ...]:
        existing = self.list_events()
        stored: list[StoredAuditEvent] = []
        for offset, event in enumerate(events, start=1):
            _validate_event(event)
            if event.payload.room_id != room_id or event.payload.revision != revision:
                raise ValueError(
                    "audit payload identity/revision must match committed room state"
                )
            sequence = len(existing) + offset
            stored.append(
                StoredAuditEvent(
                    payload=event.payload,
                    created_at_ms=event.created_at_ms,
                    public_sequence=sequence,
                    revision=revision,
                )
            )

        canonical = self.load_room_record()
        _validate_stored_event_history((*existing, *stored), canonical)
        for event in stored:
            self._executor.exec(
                """
                INSERT INTO events (
                    public_sequence, revision, event_type, event_json, created_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                """,
                event.public_sequence,
                event.revision,
                event.event_type,
                event.event_json,
                event.created_at_ms,
            )
        return tuple(stored)

    def _insert_processed_commands(
        self,
        commands: Sequence[ProcessedCommandRecord],
        *,
        committed_revision: int,
    ) -> None:
        seen_keys: set[tuple[str, str]] = set()
        for command in commands:
            _validate_processed_command(command)
            if command.revision != committed_revision:
                raise ValueError(
                    "processed command revision must equal committed room revision"
                )
            key = (command.player_id, command.command_id)
            if key in seen_keys:
                raise ProcessedCommandConflictError(
                    f"duplicate processed command in commit: {key!r}"
                )
            seen_keys.add(key)
            existing = self.get_processed_command(*key)
            if existing is not None:
                raise ProcessedCommandConflictError(
                    f"processed command already exists: {key!r}"
                )
            self._executor.exec(
                """
                INSERT INTO processed_commands (
                    player_id, command_id, request_fingerprint, revision,
                    result_json, processed_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                command.player_id,
                command.command_id,
                command.request_fingerprint,
                command.revision,
                _canonicalize_json_text(command.result_json, "result_json"),
                command.processed_at_ms,
            )

    def _insert_socket_tickets(self, tickets: Sequence[SocketTicketRecord]) -> None:
        seen_hashes: set[str] = set()
        for ticket in tickets:
            _validate_socket_ticket(ticket)
            if ticket.ticket_hash in seen_hashes:
                raise ValueError(f"duplicate socket ticket: {ticket.ticket_hash!r}")
            seen_hashes.add(ticket.ticket_hash)
            self._executor.exec(
                """
                INSERT INTO socket_tickets (
                    ticket_hash, player_id, auth_generation, expires_at_ms,
                    created_at_ms, consumed_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ticket.ticket_hash,
                ticket.player_id,
                ticket.auth_generation,
                ticket.expires_at_ms,
                ticket.created_at_ms,
                ticket.consumed_at_ms,
            )

    def _insert_player_presence(
        self, records: Sequence[PlayerPresenceRecord]
    ) -> None:
        if not records:
            return
        seen_ids: set[str] = set()
        for presence in records:
            if type(presence) is not PlayerPresenceRecord:
                raise TypeError(
                    "player presence projection must contain exact records"
                )
            _validate_player_presence(presence)
            if presence.player_id in seen_ids:
                raise ValueError(
                    f"duplicate player presence projection: {presence.player_id!r}"
                )
            seen_ids.add(presence.player_id)
            self._executor.exec(
                """
                INSERT INTO player_presence (
                    player_id, auth_generation, disconnected_at_ms,
                    disconnect_expires_at_ms
                ) VALUES (?, ?, ?, ?)
                """,
                presence.player_id,
                presence.auth_generation,
                presence.disconnected_at_ms,
                presence.disconnect_expires_at_ms,
            )
        self._advance_presence_version()

    def _apply_player_presence_mutation(
        self,
        *,
        upsert: PlayerPresenceRecord | None,
        clear_identities: Sequence[tuple[str, int]],
    ) -> bool:
        """Apply one public presence change and bump its version at most once."""

        changed = False
        if upsert is not None:
            rows = _rows(
                self._executor.exec(
                    """
                    SELECT player_id, auth_generation, disconnected_at_ms,
                           disconnect_expires_at_ms
                    FROM player_presence
                    WHERE player_id = ?
                    """,
                    upsert.player_id,
                )
            )
            previous = None if not rows else _player_presence_from_row(rows[0])
            # An error callback followed by close callback cannot restart or
            # extend the first disconnect grace period.
            if previous is None or previous.auth_generation != upsert.auth_generation:
                self._executor.exec(
                    """
                    INSERT INTO player_presence (
                        player_id, auth_generation, disconnected_at_ms,
                        disconnect_expires_at_ms
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(player_id) DO UPDATE SET
                        auth_generation = excluded.auth_generation,
                        disconnected_at_ms = excluded.disconnected_at_ms,
                        disconnect_expires_at_ms = excluded.disconnect_expires_at_ms
                    """,
                    upsert.player_id,
                    upsert.auth_generation,
                    upsert.disconnected_at_ms,
                    upsert.disconnect_expires_at_ms,
                )
                changed = True

        for player_id, auth_generation in clear_identities:
            rows = _rows(
                self._executor.exec(
                    """
                    DELETE FROM player_presence
                    WHERE player_id = ? AND auth_generation = ?
                    RETURNING player_id
                    """,
                    player_id,
                    auth_generation,
                )
            )
            changed = bool(rows) or changed
        if changed:
            self._advance_presence_version()
        return changed




__all__ = [
    "CloudflareSqlExecutor",
    "CorruptRoomStateError",
    "PersistenceError",
    "LobbyAuditPayload",
    "PlayerProjectionError",
    "PlayerRecord",
    "ProcessedCommandConflictError",
    "ProcessedCommandRecord",
    "ProjectedAuditEvent",
    "RevisionConflictError",
    "RoomAlreadyExistsError",
    "RoomCredentialRecord",
    "RoomNotFoundError",
    "RoomInitializedAuditPayload",
    "RoomRepository",
    "RoomStateCommittedAuditPayload",
    "RoomStateRecord",
    "SQLiteSqlExecutor",
    "SafeAuditPayload",
    "SocketTicketRecord",
    "SocketTicketUnavailableError",
    "SqliteSqlExecutor",
    "StoredAuditEvent",
    "SynchronousSqlExecutor",
    "UnsupportedSchemaVersionError",
]
