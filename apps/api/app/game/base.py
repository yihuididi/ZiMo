"""Shared modelling and canonical-serialization primitives for the game domain."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class GameModel(BaseModel):
    """Immutable, strict base model used by every persisted domain value.

    Attribute names remain conventional Python ``snake_case`` while the wire and
    persistence representation is always deterministic ``camelCase`` JSON.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        strict=True,
    )

    def canonical_data(self) -> dict[str, Any]:
        """Return the canonical JSON-ready representation of this model."""

        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
            round_trip=True,
        )

    def canonical_json(self) -> str:
        """Serialize with stable key ordering and no insignificant whitespace."""

        return json.dumps(
            self.canonical_data(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


def canonical_json(value: BaseModel) -> str:
    """Canonicalize an arbitrary Pydantic model using the domain convention."""

    if isinstance(value, GameModel):
        data = value.canonical_data()
    else:
        data = value.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
            round_trip=True,
        )
    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
