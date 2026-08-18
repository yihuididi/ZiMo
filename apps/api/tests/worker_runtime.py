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
    "player_presence",
    "players",
    "processed_commands",
    "room_credentials",
    "room_presence",
    "room_state",
    "socket_tickets",
)
_AUXILIARY_TABLES = (
    "events",
    "player_presence",
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

    async def test_expire_disconnected_player(self, player_id: str) -> str:
        """Make one existing grace deadline due, then run the real alarm path."""

        if (
            not isinstance(player_id, str)
            or not player_id
            or len(player_id) > 128
        ):
            raise TypeError("player_id must be a non-empty bounded string")

        def make_due() -> None:
            rows = list(
                self.ctx.storage.sql.exec(
                    """
                    SELECT disconnected_at_ms, disconnect_expires_at_ms
                    FROM player_presence
                    WHERE player_id = ?
                    """,
                    player_id,
                ).toArray()
            )
            if len(rows) != 1:
                raise ValueError("the requested player has no presence row")
            if _row_value(rows[0], "disconnect_expires_at_ms") is None:
                raise ValueError("the requested player has no kick deadline")
            disconnected_at_ms = int(
                _row_value(rows[0], "disconnected_at_ms")
            )
            self.ctx.storage.sql.exec(
                """
                UPDATE player_presence
                SET disconnect_expires_at_ms = ?
                WHERE player_id = ?
                """,
                disconnected_at_ms,
                player_id,
            )

        self.ctx.storage.transactionSync(make_due)
        await self.alarm()

        remaining = list(
            self.ctx.storage.sql.exec(
                """
                SELECT player_id, disconnect_expires_at_ms
                FROM player_presence
                WHERE disconnect_expires_at_ms IS NOT NULL
                ORDER BY disconnect_expires_at_ms, player_id
                LIMIT 1
                """
            ).toArray()
        )
        scheduled_alarm = await self.ctx.storage.getAlarm()
        if not remaining:
            return _json(
                {
                    "nextPlayerId": None,
                    "nextPresenceDeadlineMs": None,
                    "scheduledAlarmMs": (
                        None
                        if scheduled_alarm is None
                        else int(scheduled_alarm)
                    ),
                }
            )
        next_deadline_ms = int(
            _row_value(remaining[0], "disconnect_expires_at_ms")
        )
        return _json(
            {
                "nextPlayerId": str(_row_value(remaining[0], "player_id")),
                "nextPresenceDeadlineMs": next_deadline_ms,
                "scheduledAlarmMs": (
                    None if scheduled_alarm is None else int(scheduled_alarm)
                ),
            }
        )

    async def test_reconcile_hibernated_players(
        self, connected_player_ids_json: str
    ) -> str:
        """Run production batch reconciliation after test-controlled eviction."""

        try:
            player_ids = json.loads(connected_player_ids_json)
        except (TypeError, ValueError) as exc:
            raise TypeError("connected player IDs must be JSON") from exc
        if (
            type(player_ids) is not list
            or not 1 <= len(player_ids) <= 4
            or any(
                not isinstance(player_id, str)
                or not player_id
                or len(player_id) > 128
                for player_id in player_ids
            )
            or len(set(player_ids)) != len(player_ids)
        ):
            raise TypeError("connected player IDs have an invalid shape")

        identities: list[tuple[str, int]] = []
        for player_id in player_ids:
            rows = list(
                self.ctx.storage.sql.exec(
                    """
                    SELECT auth_generation
                    FROM players
                    WHERE player_id = ? AND left_at_ms IS NULL
                    """,
                    player_id,
                ).toArray()
            )
            if len(rows) != 1:
                raise ValueError("connected player is not active")
            identities.append(
                (player_id, int(_row_value(rows[0], "auth_generation")))
            )

        changed = self._orchestrator.reconcile_socket_presence(
            tuple(identities)
        )
        await self._reschedule_presence_alarm()
        view = self._orchestrator.view_for_player_id(
            identities[0][0], identities[0][1]
        )
        scheduled_alarm = await self.ctx.storage.getAlarm()
        return _json(
            {
                "changed": changed,
                "scheduledAlarmMs": (
                    None if scheduled_alarm is None else int(scheduled_alarm)
                ),
                "view": json.loads(view.canonical_json()),
            }
        )


__all__ = ["Default", "TestGameRoom"]
