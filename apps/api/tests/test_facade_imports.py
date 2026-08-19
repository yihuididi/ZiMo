from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys

import app.lobby as lobby
import app.room as room


LOBBY_EXPORTS = [
    "CataloguedLobbyAction",
    "LobbyAction",
    "LobbyActionKind",
    "LobbyDomainError",
    "LobbyTransition",
    "RANDOM_BOT_POLICY_ID",
    "apply_lobby_action",
    "authorize_lobby_config",
    "catalog_lobby_actions",
    "create_lobby_room",
    "join_lobby_room",
    "normalize_display_name",
    "resolve_lobby_action",
    "update_lobby_config",
]
LOBBY_SUBMODULES = ["actions", "state", "types"]

ROOM_EXPORTS = [
    "AuthenticatedPlayer",
    "CommandResult",
    "CommandViewResult",
    "DISCONNECT_GRACE_MS",
    "IssuedSocketTicket",
    "PlayerSession",
    "ProjectedEvents",
    "ProjectedRoomEvent",
    "RoomCreation",
    "RoomOrchestrator",
    "RoomServiceError",
    "SOCKET_TICKET_TTL_MS",
    "SessionEndedResult",
]
ROOM_SUBMODULES = [
    "codec",
    "commands",
    "contracts",
    "kernel",
    "orchestrator",
    "presence",
    "transport",
]


def test_package_facades_preserve_public_and_documented_direct_imports() -> None:
    assert lobby.__all__ == LOBBY_EXPORTS
    assert room.__all__ == ROOM_EXPORTS
    for name in (
        *LOBBY_EXPORTS,
        "MAX_DISPLAY_NAME_LENGTH",
        "apply_lobby_disconnect",
        "expire_disconnected_lobby_player",
        "reconcile_lobby_host",
    ):
        assert hasattr(lobby, name)
    for name in ROOM_EXPORTS:
        assert hasattr(room, name)
    for name in LOBBY_SUBMODULES:
        assert importlib.import_module(f"app.lobby.{name}")
    for name in ROOM_SUBMODULES:
        assert importlib.import_module(f"app.room.{name}")


def test_worker_style_top_level_facades_preserve_imports() -> None:
    api_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(api_root / "app")
    script = f"""
import lobby
import room
import importlib
assert lobby.__all__ == {LOBBY_EXPORTS!r}
assert room.__all__ == {ROOM_EXPORTS!r}
assert lobby.apply_lobby_disconnect
assert lobby.expire_disconnected_lobby_player
assert lobby.reconcile_lobby_host
assert room.RoomOrchestrator
for name in {LOBBY_SUBMODULES!r}:
    assert importlib.import_module(f"lobby.{{name}}")
for name in {ROOM_SUBMODULES!r}:
    assert importlib.import_module(f"room.{{name}}")
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=api_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
