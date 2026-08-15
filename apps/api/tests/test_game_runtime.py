from __future__ import annotations

import unittest

from app.game import (
    DeterministicRandomSource,
    Draw,
    FixedClock,
    NoLegalActionsError,
    PolicyId,
    PlayerId,
    PlayerObservation,
    RandomBotPolicy,
    RoomId,
    RoomStatus,
    SeatId,
    StaticAutomatedPolicySelector,
    SystemRandomSource,
    UnknownAutomatedPolicyError,
)
from app.game.config import GameConfig


def observation() -> PlayerObservation:
    return PlayerObservation(
        room_id=RoomId("room-1"),
        revision=0,
        room_status=RoomStatus.CREATED,
        ruleset_id="singapore",
        ruleset_version="0.1.0",
        state_schema_version=1,
        config=GameConfig(),
        viewer_player_id=PlayerId("player-1"),
        seats=(),
    )


class RuntimePortTests(unittest.TestCase):
    def test_fixed_clock_is_deterministic(self) -> None:
        clock = FixedClock(1_234_567)
        self.assertEqual(clock.now_ms(), 1_234_567)
        self.assertEqual(clock.now_ms(), 1_234_567)
        with self.assertRaises(ValueError):
            FixedClock(-1)

    def test_seeded_rng_is_repeatable(self) -> None:
        left = DeterministicRandomSource("fixture-seed")
        right = DeterministicRandomSource("fixture-seed")
        self.assertEqual(
            [left.randbelow(1000) for _ in range(20)],
            [right.randbelow(1000) for _ in range(20)],
        )
        left = DeterministicRandomSource(42)
        right = DeterministicRandomSource(42)
        self.assertEqual(
            left.shuffled((1, 2, 3, 4, 5)),
            right.shuffled((1, 2, 3, 4, 5)),
        )
        with self.assertRaises(ValueError):
            left.randbelow(0)
        with self.assertRaises(ValueError):
            left.randbelow(-1)

    def test_system_rng_rejects_invalid_bounds(self) -> None:
        rng = SystemRandomSource()
        for invalid in (0, -1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                rng.randbelow(invalid)

    def test_static_policy_selector_resolution_unknown_and_duplicates(self) -> None:
        policy = RandomBotPolicy()
        selector = StaticAutomatedPolicySelector((policy,))
        self.assertIs(selector.select(policy.policy_id), policy)
        with self.assertRaises(UnknownAutomatedPolicyError):
            selector.select(PolicyId("unknownPolicy"))
        with self.assertRaises(ValueError):
            StaticAutomatedPolicySelector((RandomBotPolicy(), RandomBotPolicy()))

    def test_random_bot_only_receives_observation_actions_and_rng(self) -> None:
        policy = RandomBotPolicy()
        actions = (
            Draw(seat_id=SeatId("seat-0")),
            Draw(seat_id=SeatId("seat-1")),
        )
        first = policy.choose_action(
            observation(), actions, DeterministicRandomSource(7)
        )
        second = policy.choose_action(
            observation(), actions, DeterministicRandomSource(7)
        )
        self.assertEqual(first, second)
        with self.assertRaises(NoLegalActionsError):
            policy.choose_action(observation(), (), DeterministicRandomSource(7))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
