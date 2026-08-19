"""Application-owned SQLite schema and ordered room migrations."""

from __future__ import annotations

import json
from typing import Any

if __package__ == "persistence":  # Python Workers load from the app directory.
    from game import RoomState
else:
    from ..game import RoomState

from .errors import UnsupportedSchemaVersionError
from .records import _now_ms, _require_non_negative_int
from .sql import (
    SynchronousSqlExecutor,
    row_value as _row_value,
    rows as _rows,
)


_ROOM_STATE_SINGLETON_ID = 1
_DISCONNECT_GRACE_MS = 300_000
_LATEST_SCHEMA_VERSION = 3
_MIGRATION_NAMES = {
    1: "milestone_1_foundation",
    2: "milestone_2_room_security",
    3: "milestone_2_player_presence",
}
_REQUIRED_APPLICATION_TABLES = {
    "_sql_schema_migrations",
    "events",
    "player_presence",
    "players",
    "processed_commands",
    "room_credentials",
    "room_presence",
    "room_state",
    "socket_tickets",
}


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


_MIGRATION_TWO_STATEMENTS = (
    """
    CREATE TABLE room_credentials (
        singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
        invite_token_hash TEXT NOT NULL CHECK (
            length(invite_token_hash) = 64
            AND invite_token_hash NOT GLOB '*[^0-9a-f]*'
        ),
        invite_generation INTEGER NOT NULL CHECK (invite_generation >= 0),
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
        updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= created_at_ms)
    )
    """,
    "CREATE UNIQUE INDEX players_token_hash_unique ON players(token_hash)",
    "CREATE INDEX socket_tickets_player_index ON socket_tickets(player_id)",
    "CREATE INDEX socket_tickets_expiry_index ON socket_tickets(expires_at_ms, consumed_at_ms)",
)


_MIGRATION_THREE_STATEMENTS = (
    """
    CREATE TABLE room_presence (
        singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
        presence_version INTEGER NOT NULL CHECK (presence_version >= 0)
    )
    """,
    "INSERT INTO room_presence (singleton_id, presence_version) VALUES (1, 0)",
    """
    CREATE TABLE player_presence (
        player_id TEXT PRIMARY KEY,
        auth_generation INTEGER NOT NULL CHECK (auth_generation >= 0),
        disconnected_at_ms INTEGER NOT NULL CHECK (disconnected_at_ms >= 0),
        disconnect_expires_at_ms INTEGER CHECK (
            disconnect_expires_at_ms IS NULL
            OR disconnect_expires_at_ms >= disconnected_at_ms
        )
    )
    """,
    """
    CREATE INDEX player_presence_expiry_index
    ON player_presence(disconnect_expires_at_ms)
    """,
)


def initialize_schema(
    executor: SynchronousSqlExecutor,
    *,
    applied_at_ms: int | None = None,
) -> None:
    """Apply all application SQL migrations in one synchronous transaction."""

    timestamp = _now_ms() if applied_at_ms is None else applied_at_ms
    _require_non_negative_int(timestamp, "applied_at_ms")

    def migrate() -> None:
        existing_tables = application_table_names(executor)
        if "_sql_schema_migrations" not in existing_tables and existing_tables:
            raise UnsupportedSchemaVersionError(
                "application tables exist without migration history"
            )
        executor.exec(
            """
            CREATE TABLE IF NOT EXISTS _sql_schema_migrations (
                id INTEGER PRIMARY KEY CHECK (id > 0),
                name TEXT NOT NULL,
                applied_at_ms INTEGER NOT NULL CHECK (applied_at_ms >= 0)
            )
            """
        )
        history_rows = _rows(
            executor.exec("SELECT id, name FROM _sql_schema_migrations ORDER BY id")
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

        if len(history) < 1:
            for statement in _MIGRATION_ONE_STATEMENTS:
                executor.exec(statement)
            executor.exec(
                """
                INSERT INTO _sql_schema_migrations (id, name, applied_at_ms)
                VALUES (?, ?, ?)
                """,
                1,
                _MIGRATION_NAMES[1],
                timestamp,
            )
            history.append((1, _MIGRATION_NAMES[1]))

        if len(history) < 2:
            for statement in _MIGRATION_TWO_STATEMENTS:
                executor.exec(statement)
            upgrade_room_snapshots_to_v2(executor)
            executor.exec(
                """
                INSERT INTO _sql_schema_migrations (id, name, applied_at_ms)
                VALUES (?, ?, ?)
                """,
                2,
                _MIGRATION_NAMES[2],
                timestamp,
            )
            history.append((2, _MIGRATION_NAMES[2]))

        if len(history) < 3:
            for statement in _MIGRATION_THREE_STATEMENTS:
                executor.exec(statement)
            executor.exec(
                """
                INSERT INTO player_presence (
                    player_id, auth_generation, disconnected_at_ms,
                    disconnect_expires_at_ms
                )
                SELECT player_id, auth_generation, ?,
                       CASE
                           WHEN EXISTS (
                               SELECT 1
                               FROM room_state
                               WHERE json_extract(snapshot_json, '$.status')
                                   IN ('IN_MATCH', 'FINISHED')
                           ) THEN NULL
                           ELSE ?
                       END
                FROM players
                WHERE left_at_ms IS NULL
                """,
                timestamp,
                timestamp + _DISCONNECT_GRACE_MS,
            )
            executor.exec(
                """
                UPDATE room_presence
                SET presence_version = 1
                WHERE singleton_id = ?
                  AND EXISTS (SELECT 1 FROM player_presence)
                """,
                _ROOM_STATE_SINGLETON_ID,
            )
            executor.exec(
                """
                INSERT INTO _sql_schema_migrations (id, name, applied_at_ms)
                VALUES (?, ?, ?)
                """,
                3,
                _MIGRATION_NAMES[3],
                timestamp,
            )

        actual_tables = application_table_names(executor)
        if actual_tables != _REQUIRED_APPLICATION_TABLES:
            missing = sorted(_REQUIRED_APPLICATION_TABLES - actual_tables)
            unexpected = sorted(actual_tables - _REQUIRED_APPLICATION_TABLES)
            raise UnsupportedSchemaVersionError(
                "application SQL table set is invalid; "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )

    executor.transaction(migrate)


def upgrade_room_snapshots_to_v2(executor: SynchronousSqlExecutor) -> None:
    """Rewrite v1 room JSON canonically while preserving revision/history."""

    rows = _rows(
        executor.exec(
            """
            SELECT singleton_id, snapshot_json
            FROM room_state
            WHERE state_schema_version = 1
            """
        )
    )
    for row in rows:
        try:
            value = json.loads(str(_row_value(row, "snapshot_json")))
            marker = value.get("stateSchemaVersion") if type(value) is dict else None
            if type(value) is not dict or type(marker) is not int or marker != 1:
                raise ValueError("schema metadata is inconsistent")
            match = value.get("match")
            if isinstance(match, dict) and match.get("status") == "PENDING_SETUP":
                raise ValueError("schema-v1 snapshot contains a v2-only match")
            value["stateSchemaVersion"] = 2
            state = RoomState.model_validate_json(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                strict=True,
            )
            snapshot_json = state.canonical_json()
        except Exception as exc:
            raise UnsupportedSchemaVersionError(
                "cannot upgrade a stored schema-v1 room snapshot"
            ) from exc
        executor.exec(
            """
            UPDATE room_state
            SET snapshot_json = ?, state_schema_version = 2
            WHERE singleton_id = ? AND state_schema_version = 1
            """,
            snapshot_json,
            int(_row_value(row, "singleton_id")),
        )


def application_table_names(executor: SynchronousSqlExecutor) -> set[str]:
    rows = _rows(executor.exec("SELECT name FROM sqlite_master WHERE type = 'table'"))
    return {
        name
        for row in rows
        if not (name := str(_row_value(row, "name"))).startswith("sqlite_")
        and not name.startswith(("_cf_", "__cf_"))
    }


__all__ = ["initialize_schema"]
