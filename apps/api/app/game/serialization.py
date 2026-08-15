"""Canonical room snapshot encoding helpers."""

from __future__ import annotations

from .model import RoomState


def serialize_room_state(state: RoomState) -> str:
    return state.canonical_json()


def deserialize_room_state(snapshot_json: str | bytes) -> RoomState:
    """Parse a strict, version-checked canonical room snapshot."""

    return RoomState.model_validate_json(snapshot_json, strict=True)


def canonicalize_room_snapshot(snapshot_json: str | bytes) -> str:
    return deserialize_room_state(snapshot_json).canonical_json()
