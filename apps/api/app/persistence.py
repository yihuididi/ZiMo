"""Durable, platform-neutral storage for a single Mahjong room.

``room_state`` is the only reconstruction source.  The other tables are
deliberate projections used for authentication, safe audit history,
idempotency, and short-lived socket tickets.  This module only depends on a
small synchronous SQL protocol so the same repository can run against a
SQLite-backed Durable Object or CPython's ``sqlite3`` module.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, ClassVar, Protocol, TypeAlias, TypeVar, cast

if __package__:
    from .game import RoomState
else:  # Python Workers load ``app/main.py`` modules from the app directory.
    from game import RoomState


_T = TypeVar("_T")
_ROOM_STATE_SINGLETON_ID = 1
_LATEST_SCHEMA_VERSION = 1
_MIGRATION_NAMES = {1: "milestone_1_foundation"}
_REQUIRED_APPLICATION_TABLES = {
    "_sql_schema_migrations",
    "events",
    "players",
    "processed_commands",
    "room_state",
    "socket_tickets",
}


class PersistenceError(RuntimeError):
    """Base class for repository failures with stable application meaning."""


class RoomAlreadyExistsError(PersistenceError):
    """Raised when a Durable Object has already been initialized."""


class RoomNotFoundError(PersistenceError):
    """Raised when a commit is attempted before room initialization."""


class RevisionConflictError(PersistenceError):
    """Raised when an optimistic compare-and-swap revision is stale."""

    def __init__(self, expected_revision: int, actual_revision: int | None) -> None:
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            "room revision conflict: "
            f"expected {expected_revision}, actual {actual_revision}"
        )


class CorruptRoomStateError(PersistenceError):
    """Raised when canonical state and its indexed metadata disagree."""


class UnsupportedSchemaVersionError(PersistenceError):
    """Raised when storage was written by a newer or inconsistent schema."""


class ProcessedCommandConflictError(PersistenceError):
    """Raised when a command id is reused for a different request."""


class PlayerProjectionError(PersistenceError):
    """Raised when authentication projections disagree with canonical state."""


class SynchronousSqlExecutor(Protocol):
    """The complete SQL surface used by :class:`RoomRepository`.

    ``exec`` intentionally mirrors Cloudflare's ``ctx.storage.sql.exec``
    binding convention.  ``transaction`` must invoke the callback before it
    returns and roll back all writes if the callback raises.
    """

    def exec(self, statement: str, *bindings: Any) -> Any:
        """Execute one SQL statement and return a cursor-like value."""

    def transaction(self, callback: Callable[[], _T]) -> _T:
        """Run ``callback`` in one synchronous transaction."""


class CloudflareSqlExecutor:
    """Adapter for a SQLite-backed Durable Object's synchronous storage API."""

    def __init__(self, storage: Any) -> None:
        sql = getattr(storage, "sql", None)
        if sql is None or not callable(getattr(sql, "exec", None)):
            raise TypeError("Durable Object storage must expose storage.sql.exec")

        transaction_sync = getattr(storage, "transactionSync", None)
        if transaction_sync is None:
            transaction_sync = getattr(storage, "transaction_sync", None)
        if not callable(transaction_sync):
            raise TypeError(
                "Durable Object storage must expose synchronous transactionSync"
            )

        self._sql = sql
        self._transaction_sync = transaction_sync

    def exec(self, statement: str, *bindings: Any) -> Any:
        return self._sql.exec(statement, *bindings)

    def transaction(self, callback: Callable[[], _T]) -> _T:
        return cast(_T, self._transaction_sync(callback))


class _SQLiteCursorResult:
    """Small cursor facade matching the Cloudflare methods the repository uses."""

    def __init__(self, cursor: Any) -> None:
        description = cursor.description
        if description is None:
            self._rows: list[dict[str, Any]] = []
        else:
            names = [column[0] for column in description]
            self._rows = [
                dict(zip(names, row, strict=True)) for row in cursor.fetchall()
            ]
        self.rowsWritten = max(int(cursor.rowcount), 0)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._rows)

    def toArray(self) -> list[dict[str, Any]]:  # noqa: N802 - Cloudflare API spelling
        return list(self._rows)

    def one(self) -> dict[str, Any]:
        if len(self._rows) != 1:
            raise RuntimeError(f"expected exactly one SQL row, got {len(self._rows)}")
        return self._rows[0]


class SQLiteSqlExecutor:
    """Adapter for a CPython ``sqlite3.Connection``.

    The connection is switched to explicit autocommit mode so every repository
    transaction has an unambiguous BEGIN/COMMIT boundary.  No import of
    ``sqlite3`` is needed at runtime; the supplied connection is intentionally
    duck typed.
    """

    def __init__(self, connection: Any) -> None:
        if not callable(getattr(connection, "execute", None)):
            raise TypeError("SQLite executor requires a DB-API connection")
        if bool(getattr(connection, "in_transaction", False)):
            raise ValueError("SQLite connection must not have an open transaction")
        try:
            connection.isolation_level = None
        except (AttributeError, TypeError) as exc:
            raise TypeError(
                "SQLite connection must support explicit transactions"
            ) from exc
        self._connection = connection

    def exec(self, statement: str, *bindings: Any) -> _SQLiteCursorResult:
        cursor = self._connection.execute(statement, tuple(bindings))
        return _SQLiteCursorResult(cursor)

    def transaction(self, callback: Callable[[], _T]) -> _T:
        if bool(getattr(self._connection, "in_transaction", False)):
            raise RuntimeError("nested repository transactions are not supported")

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            result = callback()
        except BaseException:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()
            return result


# A spelling-compatible alias for callers that prefer ``Sqlite``.
SqliteSqlExecutor = SQLiteSqlExecutor


@dataclass(frozen=True, slots=True)
class PlayerRecord:
    """Authentication data plus a queryable projection of a room player.

    Active rows (``left_at_ms is None``) exactly mirror canonical external
    controllers.  CAS retains historical rows after revocation, while auth
    generations and lifecycle timestamps may only move forwards.
    """

    player_id: str
    display_name: str
    role: str
    controller_json: str
    token_hash: str
    auth_generation: int
    joined_at_ms: int
    updated_at_ms: int
    seat_id: str | None = None
    left_at_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_id", _identity_text(self.player_id, "player_id")
        )
        if self.seat_id is not None:
            object.__setattr__(self, "seat_id", _identity_text(self.seat_id, "seat_id"))
        _validate_player(self)
        object.__setattr__(
            self,
            "controller_json",
            _canonicalize_json_text(self.controller_json, "controller_json"),
        )


@dataclass(frozen=True, slots=True)
class RoomInitializedAuditPayload:
    """Allow-listed public fact that a canonical room was initialized."""

    event_type: ClassVar[str] = "roomInitialized"
    room_id: str
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "room_id", _identity_text(self.room_id, "room_id"))
        _require_non_negative_int(self.revision, "revision")
        if self.revision != 0:
            raise ValueError("roomInitialized audit revision must be zero")


@dataclass(frozen=True, slots=True)
class RoomStateCommittedAuditPayload:
    """Allow-listed public fact that canonical state advanced one revision."""

    event_type: ClassVar[str] = "roomStateCommitted"
    room_id: str
    previous_revision: int
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "room_id", _identity_text(self.room_id, "room_id"))
        _require_non_negative_int(self.previous_revision, "previous_revision")
        _require_non_negative_int(self.revision, "revision")
        if self.revision != self.previous_revision + 1:
            raise ValueError("audit revision must equal previous_revision + 1")


SafeAuditPayload: TypeAlias = (
    RoomInitializedAuditPayload | RoomStateCommittedAuditPayload
)
_SAFE_AUDIT_PAYLOAD_TYPES = (
    RoomInitializedAuditPayload,
    RoomStateCommittedAuditPayload,
)


@dataclass(frozen=True, slots=True)
class ProjectedAuditEvent:
    """An allow-listed, secret-free event ready for public audit storage."""

    payload: SafeAuditPayload
    created_at_ms: int

    def __post_init__(self) -> None:
        _validate_event(self)

    @property
    def event_type(self) -> str:
        return self.payload.event_type

    @property
    def event_json(self) -> str:
        return _audit_payload_json(self.payload)


@dataclass(frozen=True, slots=True)
class StoredAuditEvent(ProjectedAuditEvent):
    """A projected event after the repository assigns its public sequence."""

    public_sequence: int
    revision: int


@dataclass(frozen=True, slots=True)
class ProcessedCommandRecord:
    """A durable idempotency result scoped to one room-local player."""

    player_id: str
    command_id: str
    request_fingerprint: str
    revision: int
    result_json: str
    processed_at_ms: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_id", _identity_text(self.player_id, "player_id")
        )
        object.__setattr__(
            self, "command_id", _identity_text(self.command_id, "command_id")
        )
        _validate_processed_command(self)
        object.__setattr__(
            self,
            "result_json",
            _canonicalize_json_text(self.result_json, "result_json"),
        )


@dataclass(frozen=True, slots=True)
class SocketTicketRecord:
    """A hashed, single-use WebSocket ticket projection."""

    ticket_hash: str
    player_id: str
    auth_generation: int
    expires_at_ms: int
    created_at_ms: int
    consumed_at_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_id", _identity_text(self.player_id, "player_id")
        )
        _validate_socket_ticket(self)


@dataclass(frozen=True, slots=True)
class RoomStateRecord:
    """Canonical state together with the duplicated indexed metadata."""

    state: RoomState
    snapshot_json: str
    room_id: str
    ruleset_id: str
    ruleset_version: str
    state_schema_version: int
    revision: int
    config_json: str
    created_at_ms: int
    updated_at_ms: int


_MIGRATION_ONE_STATEMENTS = (
    """
    CREATE TABLE room_state (
        singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
        room_id TEXT NOT NULL UNIQUE,
        snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
        ruleset_id TEXT NOT NULL,
        ruleset_version TEXT NOT NULL,
        state_schema_version INTEGER NOT NULL CHECK (state_schema_version > 0),
        revision INTEGER NOT NULL CHECK (revision >= 0),
        config_json TEXT NOT NULL CHECK (json_valid(config_json)),
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
        updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= created_at_ms)
    )
    """,
    """
    CREATE TABLE players (
        player_id TEXT PRIMARY KEY,
        seat_id TEXT,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL,
        controller_json TEXT NOT NULL CHECK (json_valid(controller_json)),
        token_hash TEXT NOT NULL CHECK (
            length(token_hash) = 64
            AND token_hash NOT GLOB '*[^0-9a-f]*'
        ),
        auth_generation INTEGER NOT NULL CHECK (auth_generation >= 0),
        joined_at_ms INTEGER NOT NULL CHECK (joined_at_ms >= 0),
        updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= joined_at_ms),
        left_at_ms INTEGER CHECK (
            left_at_ms IS NULL OR (
                left_at_ms >= joined_at_ms
                AND updated_at_ms >= left_at_ms
            )
        )
    )
    """,
    """
    CREATE TABLE events (
        public_sequence INTEGER PRIMARY KEY AUTOINCREMENT
            CHECK (public_sequence > 0),
        revision INTEGER NOT NULL CHECK (revision >= 0),
        event_type TEXT NOT NULL,
        event_json TEXT NOT NULL CHECK (json_valid(event_json)),
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0)
    )
    """,
    """
    CREATE TABLE processed_commands (
        player_id TEXT NOT NULL,
        command_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision >= 0),
        result_json TEXT NOT NULL CHECK (json_valid(result_json)),
        processed_at_ms INTEGER NOT NULL CHECK (processed_at_ms >= 0),
        PRIMARY KEY (player_id, command_id)
    )
    """,
    """
    CREATE TABLE socket_tickets (
        ticket_hash TEXT PRIMARY KEY CHECK (
            length(ticket_hash) = 64
            AND ticket_hash NOT GLOB '*[^0-9a-f]*'
        ),
        player_id TEXT NOT NULL,
        auth_generation INTEGER NOT NULL CHECK (auth_generation >= 0),
        expires_at_ms INTEGER NOT NULL CHECK (expires_at_ms >= 0),
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
        consumed_at_ms INTEGER CHECK (
            consumed_at_ms IS NULL OR consumed_at_ms >= created_at_ms
        )
    )
    """,
)


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

        timestamp = _now_ms() if applied_at_ms is None else applied_at_ms
        _require_non_negative_int(timestamp, "applied_at_ms")

        def migrate() -> None:
            existing_tables = self._application_table_names()
            if (
                "_sql_schema_migrations" not in existing_tables
                and existing_tables
            ):
                raise UnsupportedSchemaVersionError(
                    "application tables exist without migration history"
                )
            self._executor.exec(
                """
                CREATE TABLE IF NOT EXISTS _sql_schema_migrations (
                    id INTEGER PRIMARY KEY CHECK (id > 0),
                    name TEXT NOT NULL,
                    applied_at_ms INTEGER NOT NULL CHECK (applied_at_ms >= 0)
                )
                """
            )
            history_rows = _rows(
                self._executor.exec(
                    "SELECT id, name FROM _sql_schema_migrations ORDER BY id"
                )
            )
            history = [
                (int(_row_value(row, "id")), str(_row_value(row, "name")))
                for row in history_rows
            ]
            expected_history = [
                (migration_id, _MIGRATION_NAMES[migration_id])
                for migration_id in range(1, _LATEST_SCHEMA_VERSION + 1)
            ]
            if history != expected_history[: len(history)]:
                raise UnsupportedSchemaVersionError(
                    f"unsupported SQL migration history: {history!r}"
                )

            if not history and existing_tables - {"_sql_schema_migrations"}:
                raise UnsupportedSchemaVersionError(
                    "application tables exist without a recorded migration"
                )

            if len(history) < _LATEST_SCHEMA_VERSION:
                for statement in _MIGRATION_ONE_STATEMENTS:
                    self._executor.exec(statement)
                self._executor.exec(
                    """
                    INSERT INTO _sql_schema_migrations (id, name, applied_at_ms)
                    VALUES (?, ?, ?)
                    """,
                    1,
                    "milestone_1_foundation",
                    timestamp,
                )

            actual_tables = self._application_table_names()
            if actual_tables != _REQUIRED_APPLICATION_TABLES:
                missing = sorted(_REQUIRED_APPLICATION_TABLES - actual_tables)
                unexpected = sorted(actual_tables - _REQUIRED_APPLICATION_TABLES)
                raise UnsupportedSchemaVersionError(
                    "application SQL table set is invalid; "
                    f"missing={missing!r}, unexpected={unexpected!r}"
                )

        self._executor.transaction(migrate)

    def _application_table_names(self) -> set[str]:
        rows = _rows(
            self._executor.exec(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        )
        return {
            name
            for row in rows
            if not (name := str(_row_value(row, "name"))).startswith("sqlite_")
            and not name.startswith("__cf_")
        }

    def create_room(
        self,
        state: RoomState,
        *,
        players: Sequence[PlayerRecord] = (),
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        socket_tickets: Sequence[SocketTicketRecord] = (),
    ) -> RoomState:
        """Create the canonical room and its supplied projections atomically."""

        record = _record_from_state(state)
        state = record.state
        player_records = tuple(players)
        audit_events = tuple(events)
        command_records = tuple(processed_commands)
        ticket_records = tuple(socket_tickets)
        _validate_players_against_state(
            player_records, state, allow_historical=False
        )
        _validate_audit_events(audit_events, record)
        _validate_security_references(
            command_records, ticket_records, player_records
        )

        def create() -> None:
            if self._room_row() is not None:
                raise RoomAlreadyExistsError("room state is already initialized")
            self._insert_room_record(record)
            self._replace_players(player_records)
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
    ) -> RoomState:
        """Commit the next room revision and all projections in one transaction."""

        _require_non_negative_int(expected_revision, "expected_revision")
        record = _record_from_state(state)
        state = record.state
        player_records = None if players is None else tuple(players)
        audit_events = tuple(events)
        command_records = tuple(processed_commands)
        ticket_records = tuple(socket_tickets)
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
    ) -> RoomState:
        """Keyword-oriented alias for :meth:`compare_and_swap`."""

        return self.compare_and_swap(
            expected_revision,
            state,
            players=players,
            events=events,
            processed_commands=processed_commands,
            socket_tickets=socket_tickets,
        )

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
                left_at_ms = _row_value(row, "left_at_ms")
                records.append(
                    PlayerRecord(
                        player_id=str(_row_value(row, "player_id")),
                        seat_id=_optional_text(_row_value(row, "seat_id")),
                        display_name=str(_row_value(row, "display_name")),
                        role=str(_row_value(row, "role")),
                        controller_json=str(_row_value(row, "controller_json")),
                        token_hash=str(_row_value(row, "token_hash")),
                        auth_generation=int(_row_value(row, "auth_generation")),
                        joined_at_ms=int(_row_value(row, "joined_at_ms")),
                        updated_at_ms=int(_row_value(row, "updated_at_ms")),
                        left_at_ms=None if left_at_ms is None else int(left_at_ms),
                    )
                )
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


def _record_from_state(state: RoomState) -> RoomStateRecord:
    if not isinstance(state, RoomState):
        raise TypeError("state must be a RoomState")

    try:
        snapshot_json = state.canonical_json()
    except Exception as exc:
        raise ValueError("RoomState failed canonical serialization") from exc
    if not isinstance(snapshot_json, str):
        raise TypeError("RoomState.canonical_json() must return str")
    try:
        decoded_snapshot = json.loads(snapshot_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("RoomState.canonical_json() returned invalid JSON") from exc
    if not isinstance(decoded_snapshot, Mapping):
        raise ValueError("canonical room snapshot must be a JSON object")

    try:
        validated_state = RoomState.model_validate_json(snapshot_json, strict=True)
    except Exception as exc:
        raise ValueError(
            "RoomState canonical JSON failed strict domain validation"
        ) from exc
    validated_snapshot_json = validated_state.canonical_json()
    if validated_snapshot_json != snapshot_json:
        raise ValueError("RoomState canonical JSON changed after strict validation")
    if not _strict_value_equivalent(validated_state, state):
        raise ValueError(
            "RoomState differs from its strict canonical reconstruction"
        )

    room_id = _identity_text(validated_state.room_id, "room_id")
    ruleset_id = _identity_text(validated_state.ruleset_id, "ruleset_id")
    ruleset_version = _identity_text(
        validated_state.ruleset_version, "ruleset_version"
    )
    state_schema_version = _require_positive_int(
        validated_state.state_schema_version, "state_schema_version"
    )
    revision = _require_non_negative_int(validated_state.revision, "revision")
    created_at_ms = _require_non_negative_int(
        validated_state.created_at_ms, "created_at_ms"
    )
    updated_at_ms = _require_non_negative_int(
        validated_state.updated_at_ms, "updated_at_ms"
    )
    if updated_at_ms < created_at_ms:
        raise ValueError("updated_at_ms must be at or after created_at_ms")

    return RoomStateRecord(
        state=validated_state,
        snapshot_json=validated_snapshot_json,
        room_id=room_id,
        ruleset_id=ruleset_id,
        ruleset_version=ruleset_version,
        state_schema_version=state_schema_version,
        revision=revision,
        config_json=_canonical_json_value(validated_state.config, "config"),
        created_at_ms=created_at_ms,
        updated_at_ms=updated_at_ms,
    )


def _record_from_row(row: Any) -> RoomStateRecord:
    snapshot_json = str(_row_value(row, "snapshot_json"))
    try:
        state = RoomState.model_validate_json(snapshot_json, strict=True)
    except Exception as exc:
        raise CorruptRoomStateError("stored room snapshot is invalid") from exc
    canonical_record = _record_from_state(state)
    if canonical_record.snapshot_json != snapshot_json:
        raise CorruptRoomStateError("stored room snapshot is not canonical JSON")

    persisted = RoomStateRecord(
        state=canonical_record.state,
        snapshot_json=snapshot_json,
        room_id=str(_row_value(row, "room_id")),
        ruleset_id=str(_row_value(row, "ruleset_id")),
        ruleset_version=str(_row_value(row, "ruleset_version")),
        state_schema_version=int(_row_value(row, "state_schema_version")),
        revision=int(_row_value(row, "revision")),
        config_json=str(_row_value(row, "config_json")),
        created_at_ms=int(_row_value(row, "created_at_ms")),
        updated_at_ms=int(_row_value(row, "updated_at_ms")),
    )
    metadata_fields = (
        "room_id",
        "ruleset_id",
        "ruleset_version",
        "state_schema_version",
        "revision",
        "config_json",
        "created_at_ms",
        "updated_at_ms",
    )
    mismatches = [
        name
        for name in metadata_fields
        if getattr(persisted, name) != getattr(canonical_record, name)
    ]
    if mismatches:
        raise CorruptRoomStateError(
            "room_state metadata does not match canonical snapshot: "
            + ", ".join(mismatches)
        )
    return persisted


def _canonical_json_value(value: Any, name: str) -> str:
    if isinstance(value, str):
        return _canonicalize_json_text(value, name)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        value = model_dump(mode="json", by_alias=True, exclude_none=False)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc


def _canonicalize_json_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a JSON string")
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain valid JSON") from exc
    return _canonical_json_value(decoded, name)


def _validate_player(player: PlayerRecord) -> None:
    _require_text(player.player_id, "player_id")
    _require_text(player.display_name, "display_name")
    _require_text(player.role, "role")
    _require_sha256_hex(player.token_hash, "token_hash")
    if player.seat_id is not None:
        _require_text(player.seat_id, "seat_id")
    _canonicalize_json_text(player.controller_json, "controller_json")
    _require_non_negative_int(player.auth_generation, "auth_generation")
    _require_non_negative_int(player.joined_at_ms, "joined_at_ms")
    _require_non_negative_int(player.updated_at_ms, "updated_at_ms")
    if player.updated_at_ms < player.joined_at_ms:
        raise ValueError("player updated_at_ms must be at or after joined_at_ms")
    if player.left_at_ms is not None:
        _require_non_negative_int(player.left_at_ms, "left_at_ms")
        if player.left_at_ms < player.joined_at_ms:
            raise ValueError("player left_at_ms must be at or after joined_at_ms")
        if player.updated_at_ms < player.left_at_ms:
            raise ValueError("player updated_at_ms must be at or after left_at_ms")


def _validate_event(event: ProjectedAuditEvent) -> None:
    if type(event) not in (ProjectedAuditEvent, StoredAuditEvent):
        raise TypeError("audit event type is not allow-listed")
    if type(event.payload) not in _SAFE_AUDIT_PAYLOAD_TYPES:
        raise TypeError("audit payload type is not allow-listed")
    _require_non_negative_int(event.created_at_ms, "created_at_ms")


def _validate_audit_events(
    events: Sequence[ProjectedAuditEvent], record: RoomStateRecord
) -> None:
    for event in events:
        if type(event) is not ProjectedAuditEvent:
            raise TypeError(
                "persisted audit input must be an exact ProjectedAuditEvent"
            )
        _validate_event(event)
        if (
            event.payload.room_id != record.room_id
            or event.payload.revision != record.revision
        ):
            raise ValueError(
                "audit payload identity/revision must match committed room state"
            )


def _audit_payload_json(payload: SafeAuditPayload) -> str:
    if type(payload) is RoomInitializedAuditPayload:
        value = {
            "type": payload.event_type,
            "roomId": payload.room_id,
            "revision": payload.revision,
        }
    elif type(payload) is RoomStateCommittedAuditPayload:
        value = {
            "type": payload.event_type,
            "roomId": payload.room_id,
            "previousRevision": payload.previous_revision,
            "revision": payload.revision,
        }
    else:
        raise TypeError("audit payload type is not allow-listed")
    return _canonical_json_value(value, "audit payload")


def _parse_audit_payload(event_type: str, event_json: str) -> SafeAuditPayload:
    try:
        value = json.loads(event_json)
    except (TypeError, ValueError) as exc:
        raise CorruptRoomStateError("stored audit payload is invalid JSON") from exc
    if type(value) is not dict:
        raise CorruptRoomStateError("stored audit payload must be a JSON object")
    if value.get("type") != event_type:
        raise CorruptRoomStateError(
            "stored audit type column does not match its payload"
        )

    try:
        if event_type == RoomInitializedAuditPayload.event_type:
            if set(value) != {"type", "roomId", "revision"}:
                raise CorruptRoomStateError(
                    "roomInitialized audit payload contains non-public fields"
                )
            payload: SafeAuditPayload = RoomInitializedAuditPayload(
                room_id=value["roomId"],
                revision=value["revision"],
            )
        elif event_type == RoomStateCommittedAuditPayload.event_type:
            if set(value) != {
                "type",
                "roomId",
                "previousRevision",
                "revision",
            }:
                raise CorruptRoomStateError(
                    "roomStateCommitted audit payload contains non-public fields"
                )
            payload = RoomStateCommittedAuditPayload(
                room_id=value["roomId"],
                previous_revision=value["previousRevision"],
                revision=value["revision"],
            )
        else:
            raise CorruptRoomStateError(
                f"stored audit event type is not allow-listed: {event_type!r}"
            )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, CorruptRoomStateError):
            raise
        raise CorruptRoomStateError("stored audit payload is invalid") from exc

    if _audit_payload_json(payload) != event_json:
        raise CorruptRoomStateError("stored audit payload is not canonical JSON")
    return payload


def _validate_stored_event_history(
    events: Sequence[StoredAuditEvent],
    canonical: RoomStateRecord | None,
) -> None:
    """Validate the public log against canonical room identity and chronology."""

    if canonical is None:
        if events:
            raise CorruptRoomStateError(
                "public audit events exist without canonical room state"
            )
        return

    previous_revision = -1
    previous_created_at_ms = -1
    initialized_seen = False
    committed_revisions: set[int] = set()
    for expected_sequence, event in enumerate(events, start=1):
        if event.public_sequence != expected_sequence:
            raise CorruptRoomStateError(
                "public audit event sequence is not contiguous"
            )
        if event.payload.room_id != canonical.room_id:
            raise CorruptRoomStateError(
                "audit payload room_id does not match canonical room state"
            )
        if event.revision != event.payload.revision:
            raise CorruptRoomStateError(
                "audit payload revision does not match its indexed revision"
            )
        if event.revision > canonical.revision:
            raise CorruptRoomStateError(
                "audit event revision exceeds canonical room revision"
            )
        if event.revision < previous_revision:
            raise CorruptRoomStateError(
                "audit event revisions are not chronological"
            )
        if event.created_at_ms < previous_created_at_ms:
            raise CorruptRoomStateError(
                "audit event timestamps are not chronological"
            )

        if type(event.payload) is RoomInitializedAuditPayload:
            if initialized_seen or expected_sequence != 1:
                raise CorruptRoomStateError(
                    "roomInitialized must be the first and only initialization event"
                )
            initialized_seen = True
        elif type(event.payload) is RoomStateCommittedAuditPayload:
            if event.revision in committed_revisions:
                raise CorruptRoomStateError(
                    "roomStateCommitted audit revisions must be unique"
                )
            committed_revisions.add(event.revision)
        else:  # Defensive: StoredAuditEvent construction is otherwise public.
            raise CorruptRoomStateError("stored audit payload type is not allow-listed")

        previous_revision = event.revision
        previous_created_at_ms = event.created_at_ms


def _strict_value_equivalent(left: Any, right: Any) -> bool:
    """Compare validated domain values without string-enum coercion equality."""

    if type(left) is not type(right):
        return False
    model_fields = getattr(type(left), "model_fields", None)
    if isinstance(model_fields, Mapping):
        missing = object()
        return all(
            _strict_value_equivalent(
                getattr(left, field_name, missing),
                getattr(right, field_name, missing),
            )
            for field_name in model_fields
        )
    if isinstance(left, tuple):
        return len(left) == len(right) and all(
            _strict_value_equivalent(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_value_equivalent(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, Mapping):
        return left.keys() == right.keys() and all(
            _strict_value_equivalent(left[key], right[key]) for key in left
        )
    return bool(left == right)


def _external_roster_signature(state: RoomState) -> tuple[tuple[Any, ...], ...]:
    players_by_id = {
        _identity_text(player.player_id, "player_id"): player
        for player in state.players
    }
    signature: list[tuple[Any, ...]] = []
    for seat in state.seats:
        controller = seat.controller
        if controller is None or getattr(controller, "type", None) != "external":
            continue
        player_id = _identity_text(controller.player_id, "player_id")
        player = players_by_id[player_id]
        role = getattr(player.role, "value", player.role)
        signature.append(
            (
                player_id,
                _identity_text(seat.seat_id, "seat_id"),
                player.display_name,
                str(role),
                player.joined_at_ms,
                _canonical_json_value(controller, "seat controller"),
            )
        )
    return tuple(sorted(signature))


def _validate_players_against_state(
    players: Sequence[PlayerRecord],
    state: RoomState,
    *,
    allow_historical: bool,
) -> None:
    expected = {
        signature[0]: signature for signature in _external_roster_signature(state)
    }
    supplied: dict[str, PlayerRecord] = {}
    for player in players:
        if type(player) is not PlayerRecord:
            raise TypeError("players projection must contain exact PlayerRecord values")
        _validate_player(player)
        if player.player_id in supplied:
            raise PlayerProjectionError(
                f"duplicate player projection: {player.player_id!r}"
            )
        supplied[player.player_id] = player

    active = {
        player_id: player
        for player_id, player in supplied.items()
        if player.left_at_ms is None
    }
    historical = {
        player_id: player
        for player_id, player in supplied.items()
        if player.left_at_ms is not None
    }
    if historical and not allow_historical:
        raise PlayerProjectionError(
            "initial players projection cannot contain historical rows"
        )
    if set(active) != set(expected):
        raise PlayerProjectionError(
            "active players projection must exactly match the external player roster"
        )
    if set(historical).intersection(expected):
        raise PlayerProjectionError(
            "a historical player cannot remain in the active room roster"
        )

    for player_id, player in active.items():
        (
            _,
            seat_id,
            display_name,
            role,
            joined_at_ms,
            controller_json,
        ) = expected[player_id]
        mismatches: list[str] = []
        for field, actual, expected_value in (
            ("seat_id", player.seat_id, seat_id),
            ("display_name", player.display_name, display_name),
            ("role", player.role, role),
            ("joined_at_ms", player.joined_at_ms, joined_at_ms),
            ("controller_json", player.controller_json, controller_json),
        ):
            if actual != expected_value:
                mismatches.append(field)
        if player.left_at_ms is not None:
            mismatches.append("left_at_ms")
        if mismatches:
            raise PlayerProjectionError(
                f"player {player_id!r} projection disagrees with room state: "
                + ", ".join(mismatches)
            )


def _merge_player_lifecycle(
    existing: Sequence[PlayerRecord],
    supplied: Sequence[PlayerRecord],
    state: RoomState,
    *,
    revocation_at_ms: int,
) -> tuple[PlayerRecord, ...]:
    """Merge a complete active roster while retaining immutable revoked rows.

    Existing security counters and timestamps never regress.  A removed player
    is revoked at this commit and retained as history; only active records can
    subsequently back idempotency commands or socket tickets.
    """

    _validate_players_against_state(supplied, state, allow_historical=True)
    existing_by_id = {player.player_id: player for player in existing}
    supplied_by_id = {player.player_id: player for player in supplied}
    expected_active_ids = {
        signature[0] for signature in _external_roster_signature(state)
    }
    merged: dict[str, PlayerRecord] = {}

    for player_id, previous in existing_by_id.items():
        candidate = supplied_by_id.get(player_id)
        if previous.left_at_ms is not None:
            if candidate is not None and candidate != previous:
                raise PlayerProjectionError(
                    f"revoked player {player_id!r} history is immutable"
                )
            merged[player_id] = previous
            continue

        if player_id not in expected_active_ids:
            if candidate is None:
                revoked_at_ms = max(revocation_at_ms, previous.updated_at_ms)
                candidate = replace(
                    previous,
                    auth_generation=previous.auth_generation + 1,
                    updated_at_ms=revoked_at_ms,
                    left_at_ms=revoked_at_ms,
                )
            _validate_player_security_transition(
                previous,
                candidate,
                requires_revocation=True,
                revocation_at_ms=revocation_at_ms,
            )
            merged[player_id] = candidate
            continue

        if candidate is None:
            raise PlayerProjectionError(
                f"active player {player_id!r} is missing from supplied projections"
            )
        _validate_player_security_transition(
            previous,
            candidate,
            requires_revocation=False,
            revocation_at_ms=revocation_at_ms,
        )
        merged[player_id] = candidate

    for player_id, candidate in supplied_by_id.items():
        if player_id in merged:
            continue
        if candidate.left_at_ms is not None:
            raise PlayerProjectionError(
                f"unknown historical player projection: {player_id!r}"
            )
        merged[player_id] = candidate

    result = tuple(sorted(merged.values(), key=lambda player: player.player_id))
    _validate_players_against_state(result, state, allow_historical=True)
    return result


def _validate_player_security_transition(
    previous: PlayerRecord,
    candidate: PlayerRecord,
    *,
    requires_revocation: bool,
    revocation_at_ms: int,
) -> None:
    if candidate.joined_at_ms != previous.joined_at_ms:
        raise PlayerProjectionError("player joined_at_ms is immutable")
    if candidate.auth_generation < previous.auth_generation:
        raise PlayerProjectionError("player auth_generation cannot regress")
    if candidate.updated_at_ms < previous.updated_at_ms:
        raise PlayerProjectionError("player updated_at_ms cannot regress")
    if (
        candidate.token_hash != previous.token_hash
        and candidate.auth_generation <= previous.auth_generation
    ):
        raise PlayerProjectionError(
            "rotating a player token requires a newer auth_generation"
        )

    if requires_revocation:
        immutable_public_fields = (
            "seat_id",
            "display_name",
            "role",
            "controller_json",
        )
        if any(
            getattr(candidate, field) != getattr(previous, field)
            for field in immutable_public_fields
        ):
            raise PlayerProjectionError(
                "revoked player public history must match its active record"
            )
        if candidate.left_at_ms is None:
            raise PlayerProjectionError("removed player must have left_at_ms")
        if candidate.left_at_ms < revocation_at_ms:
            raise PlayerProjectionError(
                "removed player left_at_ms cannot precede the room commit"
            )
        if candidate.auth_generation <= previous.auth_generation:
            raise PlayerProjectionError(
                "revoking a player requires a newer auth_generation"
            )
    elif candidate.left_at_ms is not None:
        raise PlayerProjectionError("active player cannot have left_at_ms")


def _validate_security_references(
    commands: Sequence[ProcessedCommandRecord],
    tickets: Sequence[SocketTicketRecord],
    players: Sequence[PlayerRecord],
) -> None:
    active = {
        player.player_id: player
        for player in players
        if player.left_at_ms is None
    }
    for command in commands:
        if command.player_id not in active:
            raise PlayerProjectionError(
                "processed command must reference an active player"
            )
    for ticket in tickets:
        player = active.get(ticket.player_id)
        if player is None:
            raise PlayerProjectionError(
                "socket ticket must reference an active player"
            )
        if ticket.auth_generation != player.auth_generation:
            raise PlayerProjectionError(
                "socket ticket auth_generation must match its active player"
            )


def _validate_processed_command(command: ProcessedCommandRecord) -> None:
    _require_text(command.player_id, "player_id")
    _require_text(command.command_id, "command_id")
    _require_text(command.request_fingerprint, "request_fingerprint")
    _require_non_negative_int(command.revision, "revision")
    _canonicalize_json_text(command.result_json, "result_json")
    _require_non_negative_int(command.processed_at_ms, "processed_at_ms")


def _validate_socket_ticket(ticket: SocketTicketRecord) -> None:
    _require_sha256_hex(ticket.ticket_hash, "ticket_hash")
    _require_text(ticket.player_id, "player_id")
    _require_non_negative_int(ticket.auth_generation, "auth_generation")
    _require_non_negative_int(ticket.expires_at_ms, "expires_at_ms")
    _require_non_negative_int(ticket.created_at_ms, "created_at_ms")
    if ticket.expires_at_ms < ticket.created_at_ms:
        raise ValueError(
            "socket ticket expires_at_ms must be at or after created_at_ms"
        )
    if ticket.consumed_at_ms is not None:
        _require_non_negative_int(ticket.consumed_at_ms, "consumed_at_ms")
        if ticket.consumed_at_ms < ticket.created_at_ms:
            raise ValueError(
                "socket ticket consumed_at_ms must be at or after created_at_ms"
            )


def _rows(cursor: Any) -> list[Any]:
    to_array = getattr(cursor, "toArray", None)
    if callable(to_array):
        return list(to_array())
    to_array = getattr(cursor, "to_array", None)
    if callable(to_array):
        return list(to_array())
    fetchall = getattr(cursor, "fetchall", None)
    if callable(fetchall):
        return list(fetchall())
    if isinstance(cursor, Iterable):
        return list(cursor)
    raise TypeError("SQL cursor does not expose a synchronous row iterator")


def _one(cursor: Any) -> Any:
    one = getattr(cursor, "one", None)
    if callable(one):
        return one()
    rows = _rows(cursor)
    if len(rows) != 1:
        raise CorruptRoomStateError(f"expected one SQL row, found {len(rows)}")
    return rows[0]


def _row_value(row: Any, name: str) -> Any:
    if isinstance(row, Mapping):
        return row[name]
    try:
        return row[name]
    except (KeyError, TypeError, IndexError):
        try:
            return getattr(row, name)
        except AttributeError as exc:
            raise CorruptRoomStateError(f"SQL row is missing column {name!r}") from exc


def _rows_written(cursor: Any) -> int | None:
    value = getattr(cursor, "rowsWritten", None)
    if value is None:
        value = getattr(cursor, "rows_written", None)
    if callable(value):
        value = value()
    return None if value is None else int(value)


def _identity_text(value: Any, name: str) -> str:
    root = getattr(value, "root", None)
    if isinstance(root, str):
        value = root
    return str(_require_text(value, name))


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _require_sha256_hex(value: Any, name: str) -> str:
    result = _require_text(value, name)
    if len(result) != 64 or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise ValueError(
            f"{name} must be exactly 64 lowercase hexadecimal characters"
        )
    return result


def _require_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _require_positive_int(value: Any, name: str) -> int:
    result = _require_non_negative_int(value, name)
    if result == 0:
        raise ValueError(f"{name} must be positive")
    return result


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


__all__ = [
    "CloudflareSqlExecutor",
    "CorruptRoomStateError",
    "PersistenceError",
    "PlayerProjectionError",
    "PlayerRecord",
    "ProcessedCommandConflictError",
    "ProcessedCommandRecord",
    "ProjectedAuditEvent",
    "RevisionConflictError",
    "RoomAlreadyExistsError",
    "RoomNotFoundError",
    "RoomInitializedAuditPayload",
    "RoomRepository",
    "RoomStateCommittedAuditPayload",
    "RoomStateRecord",
    "SQLiteSqlExecutor",
    "SafeAuditPayload",
    "SocketTicketRecord",
    "SqliteSqlExecutor",
    "StoredAuditEvent",
    "SynchronousSqlExecutor",
    "UnsupportedSchemaVersionError",
]
