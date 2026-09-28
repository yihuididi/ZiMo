"""A registered ruleset controls engine creation and room metadata."""

from __future__ import annotations

import sqlite3

import pytest

from app.game import GameConfig, RoomState, rules_for_id
from app.game.rules import _RULESETS
from app.persistence import RoomRepository
from app.room import RoomOrchestrator


class AlternateEngine:
    capabilities = ("multiplayerLobby",)

    def setup_match(self, state):
        raise AssertionError("setup was not requested")

    def transition(self, state, action):
        raise AssertionError("transition was not requested")

    def legal_actions(self, state, seat_id):
        return ()

    def resolve_discard_window(self, state, window_id):
        raise AssertionError("resolution was not requested")


class AlternateRules:
    ruleset_id = "alternate"
    capabilities = ("multiplayerLobby",)

    def __init__(self) -> None:
        self.engines: list[AlternateEngine] = []

    def default_config(self) -> GameConfig:
        return GameConfig()

    def normalize_config(self, value: GameConfig | dict[str, object]) -> GameConfig:
        return GameConfig.normalized(value)

    def validate_snapshot(
        self, room: RoomState, *, require_deadline: bool = True
    ) -> None:
        if room.ruleset_id != self.ruleset_id:
            raise ValueError("wrong ruleset")

    def create_engine(self, rng) -> AlternateEngine:
        engine = AlternateEngine()
        self.engines.append(engine)
        return engine


def test_registered_ruleset_selects_engine_for_new_and_reloaded_rooms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules = AlternateRules()
    monkeypatch.setitem(_RULESETS, rules.ruleset_id, rules)
    connection = sqlite3.connect(":memory:")
    repository = RoomRepository.from_sqlite(connection)
    repository.initialize_schema()

    service = RoomOrchestrator(repository, ruleset_id=rules.ruleset_id)
    created = service.create_room("alternate-room", "Host")
    assert created.view.ruleset_id == rules.ruleset_id
    assert created.view.capabilities == rules.capabilities
    assert isinstance(service._game_engine, AlternateEngine)
    assert rules_for_id(rules.ruleset_id) is rules

    reloaded = RoomOrchestrator(repository)
    state = reloaded.load_room()
    assert state is not None and state.ruleset_id == rules.ruleset_id
    assert isinstance(reloaded._engine_for(state), AlternateEngine)
    assert len(rules.engines) == 2
    connection.close()


def test_unknown_ruleset_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported ruleset"):
        rules_for_id("unregistered")
