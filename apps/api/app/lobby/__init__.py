"""Stable public facade for pure lobby policy and transitions."""

from __future__ import annotations

from .actions import (
    apply_lobby_action,
    catalog_lobby_actions,
    resolve_lobby_action,
)
from .state import (
    apply_lobby_disconnect,
    authorize_lobby_config,
    create_lobby_room,
    expire_disconnected_lobby_player,
    join_lobby_room,
    normalize_display_name,
    reconcile_lobby_host,
    update_lobby_config,
)
from .types import (
    CataloguedLobbyAction,
    LobbyAction,
    LobbyActionKind,
    LobbyDomainError,
    LobbyTransition,
    MAX_DISPLAY_NAME_LENGTH,
    RANDOM_BOT_POLICY_ID,
)


__all__ = [
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
