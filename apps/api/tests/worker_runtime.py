"""Test-only Python Worker exports for Durable Object storage acceptance tests.

The production ``GameRoom`` intentionally exposes no SQL diagnostics.  This
subclass adds a narrow, fixed-shape RPC surface solely to let the Wrangler
integration harness verify the runtime schema and prove that auxiliary rows
are not reconstruction sources.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from main import Default, GameRoom


_APPLICATION_TABLES = (
    "_sql_schema_migrations",
    "events",
    "players",
    "processed_commands",
    "room_state",
    "socket_tickets",
)
_AUXILIARY_TABLES = (
    "events",
    "players",
    "processed_commands",
    "socket_tickets",
)
_FIXTURE_TIME_MS = 1_700_000_000_000


def _row_value(row: Any, column: str) -> Any:
    if isinstance(row, Mapping):
        return row[column]
    try:
        return row[column]
    except (KeyError, TypeError, IndexError):
        return getattr(row, column)


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


class TestGameRoom(GameRoom):
    """Production adapter plus fixed test-only SQLite inspection RPCs."""

    async def test_table_names(self) -> str:
        rows = list(
            self.ctx.storage.sql.exec(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).toArray()
        )
        return _json([str(_row_value(row, "name")) for row in rows])

    async def test_storage_counts(self) -> str:
        counts: dict[str, int] = {}
        for table in _APPLICATION_TABLES:
            row = self.ctx.storage.sql.exec(
                f'SELECT COUNT(*) AS row_count FROM "{table}"'
            ).one()
            counts[table] = int(_row_value(row, "row_count"))
        return _json(counts)

    async def test_seed_auxiliary_rows(self) -> str:
        def seed() -> None:
            sql = self.ctx.storage.sql
            sql.exec(
                """
                INSERT INTO players (
                    player_id, seat_id, display_name, role, controller_json,
                    token_hash, auth_generation, joined_at_ms, updated_at_ms,
                    left_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                "worker-test-player",
                "seat-0",
                "Worker Test Player",
                "MEMBER",
                '{"playerId":"worker-test-player","type":"external"}',
                "a" * 64,
                1,
                _FIXTURE_TIME_MS,
                _FIXTURE_TIME_MS,
                None,
            )
            sql.exec(
                """
                INSERT INTO events (
                    public_sequence, revision, event_type, event_json,
                    created_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                """,
                1,
                0,
                "roomInitialized",
                '{"revision":0,"roomId":"milestone-1-reconstruction","type":"roomInitialized"}',
                _FIXTURE_TIME_MS,
            )
            sql.exec(
                """
                INSERT INTO processed_commands (
                    player_id, command_id, request_fingerprint, revision,
                    result_json, processed_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                "worker-test-player",
                "worker-test-command",
                "c" * 64,
                0,
                "{}",
                _FIXTURE_TIME_MS,
            )
            sql.exec(
                """
                INSERT INTO socket_tickets (
                    ticket_hash, player_id, auth_generation, expires_at_ms,
                    created_at_ms, consumed_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                "b" * 64,
                "worker-test-player",
                1,
                _FIXTURE_TIME_MS + 30_000,
                _FIXTURE_TIME_MS,
                None,
            )

        self.ctx.storage.transactionSync(seed)
        return await self.test_storage_counts()

    async def test_clear_auxiliary_rows(self) -> str:
        def clear() -> None:
            sql = self.ctx.storage.sql
            for table in _AUXILIARY_TABLES:
                sql.exec(f'DELETE FROM "{table}"')

        self.ctx.storage.transactionSync(clear)
        return await self.test_storage_counts()


__all__ = ["Default", "TestGameRoom"]
