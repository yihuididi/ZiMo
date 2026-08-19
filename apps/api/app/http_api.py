"""FastAPI routes and middleware for the room HTTP boundary."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware

if __package__:
    from .config import Settings
    from .game import GameConfig
    from .observability import log_unexpected
    from .room.transport import (
        ApiProblem,
        COMMAND_ID,
        NATIVE_ROOM_ID,
        ROOM_PATH_PREFIX,
        canonical_json,
        parse_bearer,
        rpc_call,
    )
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from config import Settings
    from game import GameConfig
    from observability import log_unexpected
    from room.transport import (
        ApiProblem,
        COMMAND_ID,
        NATIVE_ROOM_ID,
        ROOM_PATH_PREFIX,
        canonical_json,
        parse_bearer,
        rpc_call,
    )


_GAME_CONFIG_KEYS = frozenset(
    field.alias or name for name, field in GameConfig.model_fields.items()
)


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
    invite_token: str
    display_name: str


class CommandRequest(WireModel):
    command_id: str = Field(pattern=COMMAND_ID.pattern)
    expected_revision: int = Field(ge=0)
    action_id: str = Field(min_length=1, max_length=256)


class ConfigRequest(WireModel):
    expected_revision: int = Field(ge=0)
    config: dict[str, Any]

    @field_validator("config")
    @classmethod
    def require_complete_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != _GAME_CONFIG_KEYS:
            raise ValueError("config must contain the complete GameConfig shape")
        return value


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

        token = parse_bearer(Headers(scope=scope).get("authorization"))
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
            if room_id is None or not NATIVE_ROOM_ID.fullmatch(room_id):
                raise ApiProblem(404, "roomNotFound", "The room was not found.")
            env = scope.get("env")
            namespace = getattr(env, "GAME_ROOM", None) if env is not None else None
            if namespace is None:
                raise RuntimeError("GAME_ROOM binding is unavailable")
            native_id = namespace.idFromString(room_id)
            stub = namespace.get(native_id)
            await rpc_call(stub, "authenticate_room_player", token)
        except ApiProblem as problem:
            response = JSONResponse(
                status_code=problem.status_code,
                content=problem.content(),
            )
            await response(scope, receive, send)
            return
        except Exception as exc:
            log_unexpected("http.authentication", exc)
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
        if not isinstance(path, str) or not path.startswith(f"{ROOM_PATH_PREFIX}/"):
            return False
        remainder = path[len(ROOM_PATH_PREFIX) :]
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
        prefix = f"{ROOM_PATH_PREFIX}/"
        if not path.startswith(prefix):
            return None
        return path[len(prefix) :].partition("/")[0] or None


app = FastAPI(
    title="Mahjong API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(RoomBearerMiddleware)
app.add_middleware(EnvironmentCORSMiddleware)
app.add_middleware(RoomNoStoreMiddleware)


def _is_room_path(path: str) -> bool:
    return path == ROOM_PATH_PREFIX or path.startswith(f"{ROOM_PATH_PREFIX}/")


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
    request: Request, exc: Exception
) -> JSONResponse:
    log_unexpected("http.exception", exc)
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
        credential = parse_bearer(request.headers.get("authorization"))
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
    if not NATIVE_ROOM_ID.fullmatch(room_id):
        raise ApiProblem(404, "roomNotFound", "The room was not found.")
    namespace = _namespace(request)
    try:
        native_id = namespace.idFromString(room_id)
        return namespace.get(native_id)
    except Exception as exc:
        log_unexpected("http.room_lookup", exc)
        raise ApiProblem(404, "roomNotFound", "The room was not found.") from exc


def _new_room_stub(request: Request) -> tuple[str, Any]:
    namespace = _namespace(request)
    native_id = namespace.newUniqueId()
    room_id = str(native_id.toString())
    if not NATIVE_ROOM_ID.fullmatch(room_id):  # pragma: no cover - runtime guard
        raise RuntimeError("Cloudflare returned an invalid Durable Object id")
    return room_id, namespace.get(native_id)


@app.post("/rooms", status_code=201)
async def create_room(body: CreateRoomRequest, request: Request) -> JSONResponse:
    room_id, stub = _new_room_stub(request)
    data = await rpc_call(stub, "create_room", room_id, body.display_name)
    return JSONResponse(status_code=201, content=data)


@app.post("/rooms/{room_id}/join", status_code=201)
async def join_room(
    room_id: str, body: JoinRoomRequest, request: Request
) -> JSONResponse:
    stub = _existing_room_stub(request, room_id)
    data = await rpc_call(
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
    data = await rpc_call(stub, "authenticated_view", token)
    return JSONResponse(content=data)


@app.post("/rooms/{room_id}/commands")
async def send_command(
    room_id: str, body: CommandRequest, request: Request
) -> JSONResponse:
    token = _require_bearer(request)
    stub = _existing_room_stub(request, room_id)
    data = await rpc_call(
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
    data = await rpc_call(
        stub,
        "update_config",
        token,
        body.expected_revision,
        canonical_json(body.config),
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
    data = await rpc_call(
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
    data = await rpc_call(stub, "issue_socket_ticket", token)
    return JSONResponse(content=data)


__all__ = ["app"]
