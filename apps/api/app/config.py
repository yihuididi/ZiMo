import os
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


LOCAL_FRONTEND_ORIGIN = "http://localhost:5173"


def _read_environment_value(env: Any, name: str) -> str | None:
    value: Any = None

    if isinstance(env, Mapping):
        value = env.get(name)
    elif env is not None:
        try:
            value = getattr(env, name)
        except (AttributeError, TypeError):
            value = None

    if value is None:
        value = os.environ.get(name)

    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


class Settings(BaseModel):
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    frontend_origin: str | None = None

    @classmethod
    def from_environment(cls, env: Any = None) -> "Settings":
        return cls(
            supabase_url=_read_environment_value(env, "SUPABASE_URL"),
            supabase_publishable_key=_read_environment_value(
                env, "SUPABASE_PUBLISHABLE_KEY"
            ),
            frontend_origin=_read_environment_value(env, "FRONTEND_ORIGIN"),
        )

    @property
    def cors_origins(self) -> list[str]:
        # A credential-capable room API must never reflect or broaden origins.
        # Local development gets the same single-origin policy as production.
        return [(self.frontend_origin or LOCAL_FRONTEND_ORIGIN).rstrip("/")]

    @property
    def supabase_is_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)
