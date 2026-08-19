"""Stable public facade for Mahjong room persistence.

The Worker loads this module both as ``app.persistence`` and as top-level
``persistence``. Keep the dual import form so both runtimes expose the same
public API while implementation details live in focused modules.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, ClassVar, Protocol, TypeAlias, TypeVar, cast

if __package__ == "persistence":  # Python Workers load from the app directory.
    from game import RoomState
else:
    from ..game import RoomState

from .records import (
    _LOBBY_AUDIT_EVENT_TYPES,
    _SAFE_AUDIT_PAYLOAD_TYPES,
    _audit_payload_json,
    _canonical_json_value,
    _canonicalize_json_text,
    _identity_text,
    _now_ms,
    _optional_text,
    _parse_audit_payload,
    _player_presence_from_row,
    _player_record_from_row,
    _require_non_negative_int,
    _require_positive_int,
    _require_sha256_hex,
    _require_text,
    _validate_event,
    _validate_player,
    _validate_player_presence,
    _validate_processed_command,
    _validate_public_event_details,
    _validate_room_credential,
    _validate_socket_ticket,
)
from .repository import *  # noqa: F403
from .repository import PlayerPresenceRecord, __all__
from .schema import (
    _DISCONNECT_GRACE_MS,
    _LATEST_SCHEMA_VERSION,
    _MIGRATION_NAMES,
    _MIGRATION_ONE_STATEMENTS,
    _MIGRATION_THREE_STATEMENTS,
    _MIGRATION_TWO_STATEMENTS,
    _REQUIRED_APPLICATION_TABLES,
    _ROOM_STATE_SINGLETON_ID,
)
from .sql import (
    _SQLiteCursorResult,
    _T,
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
    _strict_value_equivalent,
    _validate_audit_events,
    _validate_connected_presence_references,
    _validate_player_security_transition,
    _validate_players_against_state,
    _validate_presence_references,
    _validate_room_credential_transition,
    _validate_security_references,
    _validate_stored_event_history,
)
