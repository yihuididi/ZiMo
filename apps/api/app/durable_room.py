"""Cloudflare Durable Object adapter for one authoritative room."""

from __future__ import annotations

import json
from typing import Any

from workers import DurableObject, Response as WorkerResponse

if __package__:
    from .config import Settings
    from .observability import log_unexpected
    from .persistence import RoomRepository
    from .room import RoomOrchestrator
    from .room.transport import (
        WS_PROTOCOL,
        canonical_data,
        canonical_json,
        method_text,
        request_header,
        rpc_failure,
        rpc_success,
        service_error_data,
        socket_ticket_protocol,
        worker_problem,
    )
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from config import Settings
    from observability import log_unexpected
    from persistence import RoomRepository
    from room import RoomOrchestrator
    from room.transport import (
        WS_PROTOCOL,
        canonical_data,
        canonical_json,
        method_text,
        request_header,
        rpc_failure,
        rpc_success,
        service_error_data,
        socket_ticket_protocol,
        worker_problem,
    )


class GameRoom(DurableObject):
    """Cloudflare adapter for one authoritative, SQLite-backed room."""

    def __init__(self, ctx: Any, env: Any) -> None:
        super().__init__(ctx, env)

        repository = RoomRepository.from_durable_storage(self.ctx.storage)
        self._orchestrator = RoomOrchestrator(repository)

        async def initialize_schema() -> None:
            repository.initialize_schema()
            _live, presence_changed = self._reconcile_open_socket_presence()
            await self._reschedule_presence_alarm()
            if presence_changed:
                self._broadcast_views()

        self.ctx.blockConcurrencyWhile(initialize_schema)

    async def initialize_room(self, snapshot_json: str) -> str:
        """Persist a canonical snapshot through the retained internal RPC."""
        state = self._orchestrator.initialize_room(snapshot_json)
        return state.canonical_json()

    async def load_room(self) -> str | None:
        """Load a canonical snapshot through the retained internal RPC."""
        state = self._orchestrator.load_room()
        return state.canonical_json() if state is not None else None

    def _revision(self) -> int | None:
        state = self._orchestrator.cached_state
        if state is None:
            state = self._orchestrator.load_room()
        return None if state is None else state.revision

    def _cached_revision(self) -> int | None:
        state = self._orchestrator.cached_state
        return None if state is None else state.revision

    def _room_rpc(
        self,
        operation: Any,
        *,
        broadcast_after_change: bool = False,
    ) -> str:
        commit_generation = self._orchestrator.commit_generation
        try:
            value = operation()
            if (
                broadcast_after_change
                and self._orchestrator.commit_generation != commit_generation
            ):
                try:
                    self._broadcast_views()
                except Exception as exc:
                    log_unexpected(
                        "room.broadcast",
                        exc,
                        revision=self._cached_revision(),
                    )
                    # A committed REST mutation remains authoritative even if
                    # a best-effort push fails; clients refetch on reconnect.
                    pass
        except Exception as exc:
            failure = rpc_failure(exc)
            if failure is None:
                log_unexpected(
                    "room.rpc",
                    exc,
                    revision=self._cached_revision(),
                )
                failure = canonical_json(
                    {
                        "error": {
                            "code": "internalError",
                            "message": "The request could not be completed.",
                            "status": 500,
                        },
                        "ok": False,
                    }
                )
            return failure
        return rpc_success(value)

    async def create_room(self, room_id: str, display_name: str) -> str:
        commit_generation = self._orchestrator.commit_generation
        result = self._room_rpc(
            lambda: self._orchestrator.create_room(room_id, display_name),
            broadcast_after_change=True,
        )
        if self._orchestrator.commit_generation != commit_generation:
            await self._reschedule_presence_alarm()
        return result

    async def join_room(self, invite_token: str, display_name: str) -> str:
        commit_generation = self._orchestrator.commit_generation
        result = self._room_rpc(
            lambda: self._orchestrator.join_room(invite_token, display_name),
            broadcast_after_change=True,
        )
        if self._orchestrator.commit_generation != commit_generation:
            await self._reschedule_presence_alarm()
        return result

    async def authenticated_view(self, player_token: str) -> str:
        return self._room_rpc(
            lambda: self._orchestrator.authenticated_view(player_token)
        )

    async def authenticate_room_player(self, player_token: str) -> str:
        return self._room_rpc(
            lambda: self._orchestrator.authenticate_room_player(player_token)
        )

    async def execute_command(
        self,
        player_token: str,
        command_id: str,
        expected_revision: int,
        action_id: str,
    ) -> str:
        commit_generation = self._orchestrator.commit_generation
        result = self._room_rpc(
            lambda: self._orchestrator.execute_command(
                player_token,
                command_id,
                expected_revision,
                action_id,
            ),
            broadcast_after_change=True,
        )
        if self._orchestrator.commit_generation != commit_generation:
            await self._reschedule_presence_alarm()
        return result

    async def update_config(
        self,
        player_token: str,
        expected_revision: int,
        config_json: str,
    ) -> str:
        return self._room_rpc(
            lambda: self._orchestrator.update_config(
                player_token,
                expected_revision,
                config_json,
            ),
            broadcast_after_change=True,
        )

    async def projected_events(
        self,
        player_token: str,
        after_sequence: int,
    ) -> str:
        return self._room_rpc(
            lambda: self._orchestrator.projected_events(
                player_token,
                after_sequence,
            )
        )

    async def issue_socket_ticket(self, player_token: str) -> str:
        return self._room_rpc(
            lambda: self._orchestrator.issue_socket_ticket(player_token)
        )

    async def fetch(self, request: Any) -> WorkerResponse:
        if (
            method_text(request) != "GET"
            or (request_header(request, "upgrade") or "").casefold()
            != "websocket"
        ):
            return worker_problem(
                422,
                "invalidWebSocketRequest",
                "A WebSocket upgrade is required.",
            )

        expected_origin = Settings.from_environment(self.env).cors_origins[0]
        if request_header(request, "origin") != expected_origin:
            return worker_problem(
                403,
                "originDenied",
                "The request origin is not allowed.",
            )

        try:
            if self._orchestrator.load_room() is None:
                return worker_problem(
                    404,
                    "roomNotFound",
                    "The room was not found.",
                )
        except Exception as exc:
            log_unexpected("room.websocket_load", exc)
            return worker_problem(
                500,
                "internalError",
                "The request could not be completed.",
            )

        ticket = socket_ticket_protocol(request)
        if ticket is None:
            return worker_problem(
                401,
                "invalidSocketTicket",
                "The socket ticket protocol is invalid.",
            )

        try:
            identity = self._orchestrator.consume_socket_ticket(ticket)
        except Exception as exc:
            error = service_error_data(exc)
            if error is None:
                log_unexpected(
                    "room.websocket_ticket",
                    exc,
                    revision=self._cached_revision(),
                )
                return worker_problem(
                    500,
                    "internalError",
                    "The request could not be completed.",
                )
            return worker_problem(
                error["status"],
                error["code"],
                error["message"],
                current_revision=error.get("currentRevision"),
            )

        from js import WebSocketPair

        client, server = WebSocketPair.new().object_values()
        self.ctx.acceptWebSocket(server)
        server.serializeAttachment(
            canonical_json(
                {
                    "authGeneration": identity.auth_generation,
                    "playerId": str(identity.player_id),
                }
            )
        )
        try:
            _live, presence_changed = self._reconcile_open_socket_presence(
                include_identity=(
                    str(identity.player_id),
                    identity.auth_generation,
                )
            )
            await self._reschedule_presence_alarm()
            if presence_changed:
                self._broadcast_views()
            else:
                view = self._orchestrator.view_for_player_id(
                    identity.player_id,
                    identity.auth_generation,
                )
                server.send(_room_view_frame(view))
        except Exception as exc:
            _close_socket(server, 1011, "Connection setup failed")
            error = service_error_data(exc)
            if error is None:
                log_unexpected(
                    "room.websocket_setup",
                    exc,
                    revision=self._cached_revision(),
                )
                return worker_problem(
                    500,
                    "internalError",
                    "The request could not be completed.",
                )
            return worker_problem(
                error["status"],
                error["code"],
                error["message"],
                current_revision=error.get("currentRevision"),
            )
        return WorkerResponse(
            None,
            status=101,
            headers={
                "Cache-Control": "no-store",
                "Sec-WebSocket-Protocol": WS_PROTOCOL,
            },
            web_socket=client,
        )

    async def _reschedule_presence_alarm(self) -> None:
        """Point the room's sole alarm at its earliest durable expiry."""

        deadline_ms = self._orchestrator.next_presence_alarm_ms()
        current_alarm = await self.ctx.storage.getAlarm()
        if deadline_ms is None:
            if current_alarm is not None:
                await self.ctx.storage.deleteAlarm()
            return
        if current_alarm is None or int(current_alarm) != deadline_ms:
            await self.ctx.storage.setAlarm(deadline_ms)

    def _open_socket_identities(self) -> set[tuple[str, int]]:
        """Rediscover live identities without relying on in-memory socket state."""

        identities: set[tuple[str, int]] = set()
        for socket in self.ctx.getWebSockets():
            if not _socket_is_open(socket):
                continue
            attachment = _socket_attachment(socket)
            if attachment is None:
                _close_socket(socket, 1011, "Invalid connection state")
                continue
            identities.add(
                (attachment["playerId"], attachment["authGeneration"])
            )
        return identities

    def _reconcile_open_socket_presence(
        self,
        *,
        include_identity: tuple[str, int] | None = None,
    ) -> tuple[set[tuple[str, int]], bool]:
        """Atomically reconcile live sockets restored after a wake or upgrade."""

        confirmed_live: set[tuple[str, int]] = set()
        discovered = self._open_socket_identities()
        if include_identity is not None:
            discovered.add(include_identity)
        for identity in sorted(discovered):
            if not self._orchestrator.active_socket_identity(*identity):
                self._close_identity_sockets(identity)
                continue
            confirmed_live.add(identity)
        presence_changed = self._orchestrator.reconcile_socket_presence(
            tuple(sorted(confirmed_live))
        )
        return confirmed_live, presence_changed

    async def _socket_departed(self, identity: tuple[str, int] | None) -> None:
        if identity is None:
            return
        if identity in self._open_socket_identities():
            return
        try:
            presence_changed = self._orchestrator.player_disconnected(
                *identity,
                connected_identities=tuple(
                    sorted(self._open_socket_identities())
                ),
            )
        except Exception as exc:
            error = service_error_data(exc)
            if error is not None and error["status"] == 401:
                return
            raise
        await self._reschedule_presence_alarm()
        if presence_changed:
            self._broadcast_views()

    async def alarm(self) -> None:
        """Expire due offline players and reschedule the earliest remaining one."""

        confirmed_live, presence_changed = self._reconcile_open_socket_presence()
        expired_player_ids = self._orchestrator.expire_disconnected_players(
            tuple(sorted(confirmed_live))
        )
        await self._reschedule_presence_alarm()
        if presence_changed or expired_player_ids:
            self._broadcast_views()

    def _close_identity_sockets(self, identity: tuple[str, int]) -> None:
        for socket in self.ctx.getWebSockets():
            attachment = _socket_attachment(socket)
            if attachment is None:
                _close_socket(socket, 1011, "Invalid connection state")
                continue
            if (
                attachment["playerId"],
                attachment["authGeneration"],
            ) == identity:
                _close_socket(socket, 4001, "Room session ended")

    def _broadcast_views(self) -> None:
        for socket in self.ctx.getWebSockets():
            attachment = _socket_attachment(socket)
            if attachment is None:
                _close_socket(socket, 1011, "Invalid connection state")
                continue
            try:
                view = self._orchestrator.view_for_player_id(
                    attachment["playerId"],
                    attachment["authGeneration"],
                )
                socket.send(_room_view_frame(view))
            except Exception as exc:
                if service_error_data(exc) is not None:
                    _close_socket(socket, 4001, "Room session ended")
                    continue
                log_unexpected(
                    "room.websocket_push",
                    exc,
                    revision=self._cached_revision(),
                )
                _close_socket(socket, 1011, "Connection update failed")

    async def webSocketMessage(  # noqa: N802
        self, socket: Any, _message: Any
    ) -> None:
        _close_socket(socket, 1008, "Server-push connection")

    async def webSocketClose(  # noqa: N802
        self,
        socket: Any,
        code: int,
        reason: str,
        _was_clean: bool,
    ) -> None:
        identity = _socket_identity(socket)
        _close_socket(socket, code, reason)
        await self._socket_departed(identity)

    async def webSocketError(  # noqa: N802
        self, socket: Any, _error: Any
    ) -> None:
        identity = _socket_identity(socket)
        _close_socket(socket, 1011, "Connection lost")
        await self._socket_departed(identity)


def _room_view_frame(view: Any) -> str:
    return canonical_json({"type": "roomView", "view": canonical_data(view)})


def _socket_attachment(socket: Any) -> dict[str, Any] | None:
    try:
        raw = socket.deserializeAttachment()
        value = json.loads(str(raw))
    except Exception:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"playerId", "authGeneration"}
        or not isinstance(value["playerId"], str)
        or not value["playerId"]
        or type(value["authGeneration"]) is not int
        or value["authGeneration"] < 0
    ):
        return None
    return value


def _socket_identity(socket: Any) -> tuple[str, int] | None:
    attachment = _socket_attachment(socket)
    if attachment is None:
        return None
    return attachment["playerId"], attachment["authGeneration"]


def _close_socket(socket: Any, code: int, reason: str) -> None:
    try:
        socket.close(code, reason)
    except Exception:
        pass


def _socket_is_open(socket: Any) -> bool:
    try:
        return int(socket.readyState) == 1
    except Exception:
        return False


__all__ = ["GameRoom"]
