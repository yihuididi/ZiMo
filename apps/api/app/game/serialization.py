"""Canonical room snapshot encoding helpers."""

from __future__ import annotations

import json

from .model import RoomState


def serialize_room_state(state: RoomState) -> str:
    return state.canonical_json()


def deserialize_room_state(snapshot_json: str | bytes) -> RoomState:
    """Parse a strict, version-checked canonical room snapshot."""

    try:
        value = json.loads(snapshot_json)
    except (TypeError, ValueError):
        # Preserve Pydantic's detailed malformed-JSON error for callers.
        return RoomState.model_validate_json(snapshot_json, strict=True)
    if (
        isinstance(value, dict)
        and type(value.get("stateSchemaVersion")) is int
        and value.get("stateSchemaVersion") == 1
    ):
        match = value.get("match")
        if isinstance(match, dict) and match.get("status") == "PENDING_SETUP":
            raise ValueError("PENDING_SETUP is not valid in a schema-v1 snapshot")
        value["stateSchemaVersion"] = 2
        snapshot_json = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    return RoomState.model_validate_json(snapshot_json, strict=True)


def canonicalize_room_snapshot(snapshot_json: str | bytes) -> str:
    return deserialize_room_state(snapshot_json).canonical_json()
