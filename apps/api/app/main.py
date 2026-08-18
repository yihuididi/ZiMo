"""Cloudflare Worker and Durable Object adapters for the room service."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from workers import DurableObject, Response as WorkerResponse, WorkerEntrypoint

if __package__:
    from .config import Settings
    from .game import GameConfig
    from .persistence import RoomRepository
    from .room import RoomOrchestrator
    from .supabase_client import create_supabase_client
else:  # Python Workers load ``app/main.py`` from the app directory.
    from config import Settings
    from game import GameConfig
    from persistence import RoomRepository
    from room import RoomOrchestrator
    from supabase_client import create_supabase_client


_NATIVE_ROOM_ID = re.compile(r"^[0-9a-f]{64}$")
_CAPABILITY = re.compile(r"^[A-Za-z0-9_-]{43}$")
_COMMAND_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_ROOM_PATH_PREFIX = "/rooms"
_GAME_CONFIG_KEYS = frozenset(
    field.alias or name for name, field in GameConfig.model_fields.items()
)
_WS_PROTOCOL = "mahjong.v1"
_TICKET_PROTOCOL_PREFIX = "ticket."


def _parse_bearer(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, separator, credential = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not _CAPABILITY.fullmatch(credential)
    ):
        return None
    return credential


class WireModel(BaseModel):
    """Strict, alias-only request model for the public JSON boundary."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=False,
        strict=True,
    )


class CreateRoomRequest(WireModel):
    display_name: str


class JoinRoomRequest(WireModel):
    # Shape validation establishes that this is a string; credential validity
    # is deliberately collapsed to the same 403 response by the room service.
    invite_token: str
    display_name: str


class CommandRequest(WireModel):
    command_id: str = Field(pattern=_COMMAND_ID.pattern)
    expected_revision: int = Field(ge=0)
    # Syntactically valid but unknown handles reach the room so they receive
    # the required 409 action-conflict response rather than a shape error.
    action_id: str = Field(min_length=1, max_length=256)


class ConfigRequest(WireModel):
    expected_revision: int = Field(ge=0)
    # The domain parses this from JSON so strict tuple fields keep normal JSON
    # array semantics while still rejecting incomplete/unknown configuration.
    config: dict[str, Any]

    @field_validator("config")
    @classmethod
    def require_complete_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != _GAME_CONFIG_KEYS:
            raise ValueError("config must contain the complete GameConfig shape")
        return value


class ApiProblem(Exception):
    """A client-safe public API failure."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        current_revision: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.current_revision = current_revision
        super().__init__(message)

    def content(self) -> dict[str, dict[str, str | int]]:
        error: dict[str, str | int] = {
            "code": self.code,
            "message": self.message,
        }
        if self.current_revision is not None:
            error["currentRevision"] = self.current_revision
        return {"error": error}


class SafeCORSMiddleware(CORSMiddleware):
    """Keep rejected preflights on the same redacted error contract."""

    def preflight_response(self, request_headers: Headers) -> JSONResponse:
        response = super().preflight_response(request_headers)
        if response.status_code < 400:
            return response  # type: ignore[return-value]

        origin_allowed = self.is_allowed_origin(request_headers["origin"])
        problem = (
            ApiProblem(403, "originDenied", "The request origin is not allowed.")
            if not origin_allowed
            else ApiProblem(422, "invalidRequest", "The request is invalid.")
        )
        headers = {
            name: value
            for name, value in response.headers.items()
            if name.lower() not in {"content-length", "content-type"}
        }
        return JSONResponse(
            status_code=problem.status_code,
            content=problem.content(),
            headers=headers,
        )


class EnvironmentCORSMiddleware:
    """Resolve the one allowed frontend origin from the Worker environment."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        settings = Settings.from_environment(scope.get("env"))
        cors = SafeCORSMiddleware(
            self.app,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )
        await cors(scope, receive, send)


class RoomNoStoreMiddleware:
    """Prevent all room responses, including errors, from being cached."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or not _is_room_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        async def send_no_store(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"cache-control"
                ]
                headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_no_store)


class RoomBearerMiddleware:
    """Authenticate protected room routes before FastAPI parses their bodies."""

    _PROTECTED_SUFFIX_METHODS = {
        "": "GET",
        "/commands": "POST",
        "/config": "PATCH",
        "/events": "GET",
        "/socket-ticket": "POST",
    }

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or not self._is_protected(scope):
            await self.app(scope, receive, send)
            return

        token = _parse_bearer(Headers(scope=scope).get("authorization"))
        if token is None:
            response = JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "invalidPlayerToken",
                        "message": "Authentication is required.",
                    }
                },
            )
            await response(scope, receive, send)
            return

        try:
            room_id = self._room_id(scope)
            if room_id is None or not _NATIVE_ROOM_ID.fullmatch(room_id):
                raise ApiProblem(404, "roomNotFound", "The room was not found.")
            env = scope.get("env")
            namespace = getattr(env, "GAME_ROOM", None) if env is not None else None
            if namespace is None:
                raise RuntimeError("GAME_ROOM binding is unavailable")
            native_id = namespace.idFromString(room_id)
            stub = namespace.get(native_id)
            # This RPC performs durable player authentication before FastAPI
            # is allowed to parse a protected request body.
            await _rpc_call(stub, "authenticate_room_player", token)
        except ApiProblem as problem:
            response = JSONResponse(
                status_code=problem.status_code,
                content=problem.content(),
            )
            await response(scope, receive, send)
            return
        except Exception:
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internalError",
                        "message": "The request could not be completed.",
                    }
                },
            )
            await response(scope, receive, send)
            return

        scope["room_player_token"] = token
        await self.app(scope, receive, send)

    @classmethod
    def _is_protected(cls, scope: dict[str, Any]) -> bool:
        path = scope.get("path", "")
        if not isinstance(path, str) or not path.startswith(f"{_ROOM_PATH_PREFIX}/"):
            return False
        remainder = path[len(_ROOM_PATH_PREFIX) :]
        room_id, separator, suffix = remainder[1:].partition("/")
        if not room_id:
            return False
        normalized_suffix = f"/{suffix}" if separator else ""
        required_method = cls._PROTECTED_SUFFIX_METHODS.get(normalized_suffix)
        return required_method == str(scope.get("method", "")).upper()

    @staticmethod
    def _room_id(scope: dict[str, Any]) -> str | None:
        path = scope.get("path", "")
        if not isinstance(path, str):
            return None
        prefix = f"{_ROOM_PATH_PREFIX}/"
        if not path.startswith(prefix):
            return None
        return path[len(prefix) :].partition("/")[0] or None


app = FastAPI(
    title="Mahjong API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# Middleware is added inside-out by Starlette. Authentication therefore runs
# before route/body validation, while CORS and no-store still wrap its errors.
app.add_middleware(RoomBearerMiddleware)
app.add_middleware(EnvironmentCORSMiddleware)
app.add_middleware(RoomNoStoreMiddleware)


def _is_room_path(path: str) -> bool:
    return path == _ROOM_PATH_PREFIX or path.startswith(f"{_ROOM_PATH_PREFIX}/")


def _error_response(problem: ApiProblem) -> JSONResponse:
    return JSONResponse(status_code=problem.status_code, content=problem.content())


@app.exception_handler(ApiProblem)
async def api_problem_handler(_request: Request, exc: ApiProblem) -> JSONResponse:
    return _error_response(exc)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, _exc: RequestValidationError
) -> JSONResponse:
    if _is_room_path(request.url.path):
        return _error_response(
            ApiProblem(422, "invalidRequest", "The request is invalid.")
        )
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalidRequest", "message": "Invalid request."}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if _is_room_path(request.url.path):
        if exc.status_code == 404:
            problem = ApiProblem(404, "roomNotFound", "The room was not found.")
        elif exc.status_code == 405:
            problem = ApiProblem(422, "invalidRequest", "The request is invalid.")
        else:
            problem = ApiProblem(
                exc.status_code,
                "requestFailed",
                "The request could not be completed.",
            )
        return _error_response(problem)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request, _exc: Exception
) -> JSONResponse:
    if _is_room_path(request.url.path):
        return _error_response(
            ApiProblem(500, "internalError", "The request could not be completed.")
        )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internalError", "message": "Internal error."}},
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "mahjong-api"}


@app.get("/health")
async def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "mahjong-api"}


def _require_bearer(request: Request) -> str:
    credential = request.scope.get("room_player_token")
    if not isinstance(credential, str):
        credential = _parse_bearer(request.headers.get("authorization"))
    if credential is None:
        raise ApiProblem(401, "invalidPlayerToken", "Authentication is invalid.")
    return credential


def _namespace(request: Request) -> Any:
    env = request.scope.get("env")
    namespace = getattr(env, "GAME_ROOM", None) if env is not None else None
    if namespace is None:
        raise RuntimeError("GAME_ROOM binding is unavailable")
    return namespace


def _existing_room_stub(request: Request, room_id: str) -> Any:
    if not _NATIVE_ROOM_ID.fullmatch(room_id):
        raise ApiProblem(404, "roomNotFound", "The room was not found.")
    namespace = _namespace(request)
    try:
        native_id = namespace.idFromString(room_id)
        return namespace.get(native_id)
    except Exception as exc:
        raise ApiProblem(404, "roomNotFound", "The room was not found.") from exc


def _new_room_stub(request: Request) -> tuple[str, Any]:
    namespace = _namespace(request)
    native_id = namespace.newUniqueId()
    room_id = str(native_id.toString())
    if not _NATIVE_ROOM_ID.fullmatch(room_id):  # pragma: no cover - runtime guard
        raise RuntimeError("Cloudflare returned an invalid Durable Object id")
    return room_id, namespace.get(native_id)


async def _rpc_call(stub: Any, method_name: str, *args: Any) -> Any:
    raw = await getattr(stub, method_name)(*args)
    try:
        envelope = json.loads(str(raw))
    except (TypeError, ValueError) as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("room RPC returned invalid JSON") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("ok"), bool):
        raise RuntimeError("room RPC returned an invalid envelope")
    if envelope["ok"]:
        if "data" not in envelope:
            raise RuntimeError("room RPC success omitted data")
        return envelope["data"]

    error = envelope.get("error")
    if not isinstance(error, dict):
        raise RuntimeError("room RPC failure omitted error")
    status_code = error.get("status")
    code = error.get("code")
    message = error.get("message")
    current_revision = error.get("currentRevision")
    if (
        type(status_code) is not int
        or not isinstance(code, str)
        or not isinstance(message, str)
        or (current_revision is not None and type(current_revision) is not int)
    ):
        raise RuntimeError("room RPC returned an invalid error")
    raise ApiProblem(
        status_code,
        code,
        message,
        current_revision=current_revision,
    )


@app.post("/rooms", status_code=201)
async def create_room(body: CreateRoomRequest, request: Request) -> JSONResponse:
    room_id, stub = _new_room_stub(request)
    data = await _rpc_call(stub, "create_room", room_id, body.display_name)
    return JSONResponse(status_code=201, content=data)


@app.post("/rooms/{room_id}/join", status_code=201)
async def join_room(
    room_id: str, body: JoinRoomRequest, request: Request
) -> JSONResponse:
    stub = _existing_room_stub(request, room_id)
    data = await _rpc_call(
        stub,
        "join_room",
        body.invite_token,
        body.display_name,
    )
    return JSONResponse(status_code=201, content=data)


@app.get("/rooms/{room_id}")
async def get_room(room_id: str, request: Request) -> JSONResponse:
    token = _require_bearer(request)
    stub = _existing_room_stub(request, room_id)
    data = await _rpc_call(stub, "authenticated_view", token)
    return JSONResponse(content=data)


@app.post("/rooms/{room_id}/commands")
async def send_command(
    room_id: str, body: CommandRequest, request: Request
) -> JSONResponse:
    token = _require_bearer(request)
    stub = _existing_room_stub(request, room_id)
    data = await _rpc_call(
        stub,
        "execute_command",
        token,
        body.command_id,
        body.expected_revision,
        body.action_id,
    )
    return JSONResponse(content=data)


@app.patch("/rooms/{room_id}/config")
async def patch_config(
    room_id: str, body: ConfigRequest, request: Request
) -> JSONResponse:
    token = _require_bearer(request)
    stub = _existing_room_stub(request, room_id)
    data = await _rpc_call(
        stub,
        "update_config",
        token,
        body.expected_revision,
        _canonical_json(body.config),
    )
    return JSONResponse(content=data)


@app.get("/rooms/{room_id}/events")
async def get_events(
    room_id: str,
    request: Request,
    after_sequence: int | None = Query(default=None, alias="afterSequence", ge=0),
) -> JSONResponse:
    token = _require_bearer(request)
    stub = _existing_room_stub(request, room_id)
    data = await _rpc_call(
        stub,
        "projected_events",
        token,
        0 if after_sequence is None else after_sequence,
    )
    return JSONResponse(content=data)


@app.post("/rooms/{room_id}/socket-ticket")
async def issue_socket_ticket(room_id: str, request: Request) -> JSONResponse:
    token = _require_bearer(request)
    stub = _existing_room_stub(request, room_id)
    data = await _rpc_call(stub, "issue_socket_ticket", token)
    return JSONResponse(content=data)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_data(value: Any) -> Any:
    if hasattr(value, "canonical_data"):
        return value.canonical_data()
    if hasattr(value, "canonical_json"):
        return json.loads(value.canonical_json())
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict | list | tuple | bool | int | float) or value is None:
        return value
    raise TypeError(f"unsupported room result type: {type(value).__name__}")


def _rpc_success(value: Any) -> str:
    return _canonical_json({"data": _canonical_data(value), "ok": True})


def _service_error_data(exc: Exception) -> dict[str, Any] | None:
    """Extract only the explicitly safe room-service exception surface."""

    status_code = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None)
    current_revision = getattr(exc, "current_revision", None)
    if (
        type(status_code) is not int
        or not isinstance(code, str)
        or not isinstance(message, str)
        or (current_revision is not None and type(current_revision) is not int)
    ):
        return None
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "status": status_code,
    }
    if current_revision is not None:
        error["currentRevision"] = current_revision
    return error


def _rpc_failure(exc: Exception) -> str | None:
    error = _service_error_data(exc)
    return None if error is None else _canonical_json({"error": error, "ok": False})


def _method_text(request: Any) -> str:
    method = request.method
    return str(getattr(method, "value", method)).upper()


def _request_header(request: Any, name: str) -> str | None:
    value = request.headers.get(name)
    return None if value is None else str(value)


def _socket_ticket_protocol(request: Any) -> str | None:
    raw = _request_header(request, "sec-websocket-protocol")
    if raw is None:
        return None
    protocols = [part.strip() for part in raw.split(",") if part.strip()]
    if len(protocols) != 2 or protocols.count(_WS_PROTOCOL) != 1:
        return None
    ticket_protocols = [
        protocol
        for protocol in protocols
        if protocol.startswith(_TICKET_PROTOCOL_PREFIX)
    ]
    if len(ticket_protocols) != 1:
        return None
    ticket = ticket_protocols[0][len(_TICKET_PROTOCOL_PREFIX) :]
    return ticket if _CAPABILITY.fullmatch(ticket) else None


def _worker_problem(
    status_code: int,
    code: str,
    message: str,
    *,
    current_revision: int | None = None,
) -> WorkerResponse:
    problem = ApiProblem(
        status_code,
        code,
        message,
        current_revision=current_revision,
    )
    return WorkerResponse(
        _canonical_json(problem.content()),
        status=status_code,
        headers={
            "Cache-Control": "no-store",
            "Content-Type": "application/json",
        },
    )


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Any:
        settings = Settings.from_environment(self.env)
        app.state.settings = settings
        app.state.supabase = create_supabase_client(settings)

        ws_room_id = _websocket_room_id(request)
        if ws_room_id is not None:
            if not _NATIVE_ROOM_ID.fullmatch(ws_room_id):
                return _worker_problem(404, "roomNotFound", "The room was not found.")
            try:
                native_id = self.env.GAME_ROOM.idFromString(ws_room_id)
                stub = self.env.GAME_ROOM.get(native_id)
            except Exception:
                return _worker_problem(404, "roomNotFound", "The room was not found.")
            try:
                return await stub.fetch(request)
            except Exception:
                return _worker_problem(
                    500,
                    "internalError",
                    "The request could not be completed.",
                )

        import asgi

        return await asgi.fetch(app, request.js_object, self.env)


def _websocket_room_id(request: Any) -> str | None:
    from js import URL

    pathname = str(URL.new(request.url).pathname)
    prefix = f"{_ROOM_PATH_PREFIX}/"
    suffix = "/ws"
    if not pathname.startswith(prefix) or not pathname.endswith(suffix):
        return None
    room_id = pathname[len(prefix) : -len(suffix)]
    if "/" in room_id or not room_id:
        return ""
    return room_id


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
                except Exception:
                    # A committed REST mutation remains authoritative even if
                    # a best-effort push fails; clients refetch on reconnect.
                    pass
        except Exception as exc:
            failure = _rpc_failure(exc)
            if failure is None:
                failure = _canonical_json(
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
        return _rpc_success(value)

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
            # A leave/removal can discard a pending expiry, while starting a
            # match freezes seats and clears every kick deadline.
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
            _method_text(request) != "GET"
            or (_request_header(request, "upgrade") or "").casefold()
            != "websocket"
        ):
            return _worker_problem(
                422,
                "invalidWebSocketRequest",
                "A WebSocket upgrade is required.",
            )

        expected_origin = Settings.from_environment(self.env).cors_origins[0]
        if _request_header(request, "origin") != expected_origin:
            return _worker_problem(
                403,
                "originDenied",
                "The request origin is not allowed.",
            )

        try:
            if self._orchestrator.load_room() is None:
                return _worker_problem(
                    404,
                    "roomNotFound",
                    "The room was not found.",
                )
        except Exception:
            return _worker_problem(
                500,
                "internalError",
                "The request could not be completed.",
            )

        ticket = _socket_ticket_protocol(request)
        if ticket is None:
            return _worker_problem(
                401,
                "invalidSocketTicket",
                "The socket ticket protocol is invalid.",
            )

        try:
            identity = self._orchestrator.consume_socket_ticket(ticket)
        except Exception as exc:
            error = _service_error_data(exc)
            if error is None:
                return _worker_problem(
                    500,
                    "internalError",
                    "The request could not be completed.",
                )
            return _worker_problem(
                error["status"],
                error["code"],
                error["message"],
                current_revision=error.get("currentRevision"),
            )

        from js import WebSocketPair

        client, server = WebSocketPair.new().object_values()
        self.ctx.acceptWebSocket(server)
        server.serializeAttachment(
            _canonical_json(
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
                # Presence is projected independently of room revision, so all
                # connected viewers receive an individualized same-revision view.
                self._broadcast_views()
            else:
                view = self._orchestrator.view_for_player_id(
                    identity.player_id,
                    identity.auth_generation,
                )
                server.send(_room_view_frame(view))
        except Exception as exc:
            _close_socket(server, 1011, "Connection setup failed")
            error = _service_error_data(exc)
            if error is None:
                return _worker_problem(
                    500,
                    "internalError",
                    "The request could not be completed.",
                )
            return _worker_problem(
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
                "Sec-WebSocket-Protocol": _WS_PROTOCOL,
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
        # A player remains connected while any tab using the same credential
        # generation has an OPEN server-side socket.
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
            error = _service_error_data(exc)
            # A socket may close after its player was removed or its credential
            # generation was revoked. That close must not recreate presence.
            if error is not None and error["status"] == 401:
                return
            raise
        await self._reschedule_presence_alarm()
        if presence_changed:
            self._broadcast_views()

    async def alarm(self) -> None:
        """Expire due offline players and reschedule the earliest remaining one."""

        confirmed_live, presence_changed = (
            self._reconcile_open_socket_presence()
        )

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
                if _service_error_data(exc) is not None:
                    _close_socket(socket, 4001, "Room session ended")
                    continue
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
        # This is required by older/local runtimes and harmless once the
        # compatibility-date auto-reply has already completed the handshake.
        _close_socket(socket, code, reason)
        await self._socket_departed(identity)

    async def webSocketError(  # noqa: N802
        self, socket: Any, _error: Any
    ) -> None:
        identity = _socket_identity(socket)
        _close_socket(socket, 1011, "Connection lost")
        await self._socket_departed(identity)


def _room_view_frame(view: Any) -> str:
    return _canonical_json({"type": "roomView", "view": _canonical_data(view)})


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
        # The peer may already have closed between discovery and delivery.
        pass


def _socket_is_open(socket: Any) -> bool:
    try:
        return int(socket.readyState) == 1
    except Exception:
        return False


__all__ = ["Default", "GameRoom", "app"]
