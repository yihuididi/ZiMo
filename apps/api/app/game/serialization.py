"""Canonical room snapshot encoding helpers."""

from __future__ import annotations

from .model import RoomState
from .rules import rules_for_id


def serialize_room_state(state: RoomState) -> str:
    rules_for_id(state.ruleset_id).validate_snapshot(state)
    return state.canonical_json()


def deserialize_room_state(snapshot_json: str | bytes) -> RoomState:
    state = RoomState.model_validate_json(snapshot_json, strict=True)
    rules_for_id(state.ruleset_id).validate_snapshot(state)
    return state


def canonicalize_room_snapshot(snapshot_json: str | bytes) -> str:
    return deserialize_room_state(snapshot_json).canonical_json()
