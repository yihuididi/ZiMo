"""Cloudflare Worker entrypoint for HTTP and WebSocket routing."""

from __future__ import annotations

from typing import Any

from workers import WorkerEntrypoint

if __package__:
    from .config import Settings
    from .http_api import app
    from .observability import log_unexpected
    from .room.transport import NATIVE_ROOM_ID, ROOM_PATH_PREFIX, worker_problem
    from .supabase_client import create_supabase_client
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from config import Settings
    from http_api import app
    from observability import log_unexpected
    from room.transport import NATIVE_ROOM_ID, ROOM_PATH_PREFIX, worker_problem
    from supabase_client import create_supabase_client


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Any:
        settings = Settings.from_environment(self.env)
        app.state.settings = settings
        app.state.supabase = create_supabase_client(settings)

        ws_room_id = _websocket_room_id(request)
        if ws_room_id is not None:
            if not NATIVE_ROOM_ID.fullmatch(ws_room_id):
                return worker_problem(404, "roomNotFound", "The room was not found.")
            try:
                native_id = self.env.GAME_ROOM.idFromString(ws_room_id)
                stub = self.env.GAME_ROOM.get(native_id)
            except Exception as exc:
                log_unexpected("worker.room_lookup", exc)
                return worker_problem(404, "roomNotFound", "The room was not found.")
            try:
                return await stub.fetch(request)
            except Exception as exc:
                log_unexpected("worker.websocket_forward", exc)
                return worker_problem(
                    500,
                    "internalError",
                    "The request could not be completed.",
                )

        import asgi

        return await asgi.fetch(app, request.js_object, self.env)


def _websocket_room_id(request: Any) -> str | None:
    from js import URL

    pathname = str(URL.new(request.url).pathname)
    prefix = f"{ROOM_PATH_PREFIX}/"
    suffix = "/ws"
    if not pathname.startswith(prefix) or not pathname.endswith(suffix):
        return None
    room_id = pathname[len(prefix) : -len(suffix)]
    if "/" in room_id or not room_id:
        return ""
    return room_id


__all__ = ["Default"]
