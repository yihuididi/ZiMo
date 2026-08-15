from typing import Any

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from workers import DurableObject, Response, WorkerEntrypoint

from config import Settings
from supabase_client import create_supabase_client


class EnvironmentCORSMiddleware:
    """Resolve the deployed frontend origin from the Worker environment."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        settings = Settings.from_environment(scope.get("env"))
        cors = CORSMiddleware(
            self.app,
            allow_origins=settings.cors_origins,
            allow_methods=["GET"],
            allow_headers=["*"],
        )
        await cors(scope, receive, send)


app = FastAPI(
    title="Mahjong API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(EnvironmentCORSMiddleware)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "mahjong-api"}


@app.get("/health")
async def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "mahjong-api"}


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Any:
        settings = Settings.from_environment(self.env)
        app.state.settings = settings
        app.state.supabase = create_supabase_client(settings)

        import asgi

        return await asgi.fetch(app, request.js_object, self.env)


class GameRoom(DurableObject):
    """Deployment skeleton for a future Mahjong table."""

    async def fetch(self, request: Any) -> Response:
        return Response("GameRoom is not implemented", status=501)
