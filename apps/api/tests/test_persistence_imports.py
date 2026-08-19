from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys

import app.persistence as persistence


EXPECTED_ALL = [
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

LEGACY_DIRECT_ATTRIBUTES = [
    "RoomState",
    "_DISCONNECT_GRACE_MS",
    "_LATEST_SCHEMA_VERSION",
    "_LOBBY_AUDIT_EVENT_TYPES",
    "_MIGRATION_NAMES",
    "_MIGRATION_ONE_STATEMENTS",
    "_MIGRATION_THREE_STATEMENTS",
    "_MIGRATION_TWO_STATEMENTS",
    "_REQUIRED_APPLICATION_TABLES",
    "_ROOM_STATE_SINGLETON_ID",
    "_SAFE_AUDIT_PAYLOAD_TYPES",
    "_SQLiteCursorResult",
    "_T",
    "_audit_payload_json",
    "_canonical_json_value",
    "_canonicalize_json_text",
    "_external_roster_signature",
    "_identity_text",
    "_merge_player_lifecycle",
    "_normalize_player_identities",
    "_now_ms",
    "_one",
    "_optional_text",
    "_parse_audit_payload",
    "_player_presence_from_row",
    "_player_record_from_row",
    "_record_from_row",
    "_record_from_state",
    "_require_non_negative_int",
    "_require_positive_int",
    "_require_sha256_hex",
    "_require_text",
    "_row_value",
    "_rows",
    "_rows_written",
    "_strict_value_equivalent",
    "_validate_audit_events",
    "_validate_connected_presence_references",
    "_validate_event",
    "_validate_player",
    "_validate_player_presence",
    "_validate_player_security_transition",
    "_validate_players_against_state",
    "_validate_presence_references",
    "_validate_processed_command",
    "_validate_public_event_details",
    "_validate_room_credential",
    "_validate_room_credential_transition",
    "_validate_security_references",
    "_validate_socket_ticket",
    "_validate_stored_event_history",
]
PERSISTENCE_SUBMODULES = [
    "errors",
    "records",
    "repository",
    "schema",
    "sql",
    "validation",
]


def test_package_facade_preserves_exports_and_direct_presence_record() -> None:
    assert persistence.__all__ == EXPECTED_ALL
    assert persistence.SqliteSqlExecutor is persistence.SQLiteSqlExecutor
    assert persistence.PlayerPresenceRecord
    for name in [*EXPECTED_ALL, *LEGACY_DIRECT_ATTRIBUTES]:
        assert hasattr(persistence, name)
    for name in PERSISTENCE_SUBMODULES:
        assert importlib.import_module(f"app.persistence.{name}")


def test_worker_style_top_level_facade_preserves_exports() -> None:
    api_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(api_root / "app")
    script = f"""
import persistence
import importlib
assert persistence.__all__ == {EXPECTED_ALL!r}
assert persistence.SqliteSqlExecutor is persistence.SQLiteSqlExecutor
assert persistence.PlayerPresenceRecord
for name in persistence.__all__:
    assert hasattr(persistence, name), name
for name in {LEGACY_DIRECT_ATTRIBUTES!r}:
    assert hasattr(persistence, name), name
for name in {PERSISTENCE_SUBMODULES!r}:
    assert importlib.import_module(f"persistence.{{name}}")
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=api_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
