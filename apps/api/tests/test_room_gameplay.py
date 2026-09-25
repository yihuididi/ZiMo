from __future__ import annotations

import base64
import json
import sqlite3
import unittest

from app.game import MatchStatus, PendingDeadline, RoomStatus
from app.persistence import RoomRepository
from app.room import CommandViewResult, RoomOrchestrator, RoomServiceError


ROOM_ID = "fedcba9876543210" * 4


class ZeroRandomSource:
    """Valid deterministic permutation with seat zero and first legal choices."""

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return 0

    def shuffled(self, values):  # type: ignore[no-untyped-def]
        return tuple(values)


class DuplicateFaceRandomSource(ZeroRandomSource):
    """Deal two physical copies of the first face to seat zero."""

    def shuffled(self, values):  # type: ignore[no-untyped-def]
        source = tuple(values)
        seat_zero_tiles = (source[0], source[1], *source[4:15])
        selected = set(seat_zero_tiles)
        remaining = iter(tile for tile in source if tile not in selected)
        result = [None] * len(source)
        for index, tile in zip(range(0, 52, 4), seat_zero_tiles, strict=True):
            result[index] = tile
        for index, tile in enumerate(result):
            if tile is None:
                result[index] = next(remaining)
        return tuple(result)


class DeterministicCapabilities:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return base64.urlsafe_b64encode(bytes([self.count]) * 32).decode().rstrip("=")


class DeterministicIds:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def __call__(self, prefix: str) -> str:
        value = self.counts.get(prefix, 0) + 1
        self.counts[prefix] = value
        return f"{prefix}-{value}"


class MutableClock:
    def __init__(self, timestamp_ms: int) -> None:
        self.timestamp_ms = timestamp_ms

    def now_ms(self) -> int:
        return self.timestamp_ms


def action_for_slot(view, slot: str):  # type: ignore[no-untyped-def]
    return next(action for action in view.actions if action.presentation_slot == slot)


class RoomGameplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.repository = RoomRepository.from_sqlite(self.connection)
        self.repository.initialize_schema(applied_at_ms=900)
        self.credentials = DeterministicCapabilities()
        self.ids = DeterministicIds()
        self.clock = MutableClock(1_000)
        self.service = RoomOrchestrator(
            self.repository,
            clock=self.clock,
            credential_source=self.credentials,
            id_source=self.ids,
            random_source=ZeroRandomSource(),
        )

    def tearDown(self) -> None:
        self.connection.close()

    def at(self, timestamp_ms: int) -> RoomOrchestrator:
        self.clock.timestamp_ms = timestamp_ms
        return self.service

    def start_preview(self):  # type: ignore[no-untyped-def]
        created = self.service.create_room(ROOM_ID, "Host")
        self.service.player_connected(created.player_id, 0, now_ms=1_000)
        connected = self.service.authenticated_view(created.player_token)
        start = next(
            action
            for action in connected.actions
            if action.label == "Start Against Bots"
        )
        result = self.service.execute_command(
            created.player_token,
            "start-preview",
            0,
            start.action_id,
        )
        self.assertIsInstance(result, CommandViewResult)
        return created, result

    def discard_drawn_tile(self, created, view, command_id="discard-one"):  # type: ignore[no-untyped-def]
        action = action_for_slot(view, "drawnTile")
        result = self.service.execute_command(
            created.player_token,
            command_id,
            view.revision,
            action.action_id,
        )
        self.assertIsInstance(result, CommandViewResult)
        return action, result

    def test_setup_and_catalog_support_one_to_four_human_players(self) -> None:
        for human_count in range(1, 5):
            with self.subTest(human_count=human_count):
                connection = sqlite3.connect(":memory:")
                try:
                    repository = RoomRepository.from_sqlite(connection)
                    repository.initialize_schema(applied_at_ms=900)
                    service = RoomOrchestrator(
                        repository,
                        clock=MutableClock(1_000),
                        credential_source=DeterministicCapabilities(),
                        id_source=DeterministicIds(),
                        random_source=ZeroRandomSource(),
                    )
                    room_id = f"{human_count:064x}"
                    sessions = [service.create_room(room_id, "Player 1")]
                    for player_number in range(2, human_count + 1):
                        sessions.append(
                            service.join_room(
                                sessions[0].invite_token,
                                f"Player {player_number}",
                            )
                        )
                    for session in sessions:
                        self.assertTrue(
                            service.player_connected(
                                session.player_id,
                                0,
                                now_ms=1_000,
                            )
                        )

                    command_number = 0

                    def execute_label(session, label):  # type: ignore[no-untyped-def]
                        nonlocal command_number
                        view = service.authenticated_view(session.player_token)
                        action = next(
                            item
                            for item in view.actions
                            if item.label == label and item.enabled
                        )
                        command_number += 1
                        result = service.execute_command(
                            session.player_token,
                            f"matrix-{human_count}-{command_number}",
                            view.revision,
                            action.action_id,
                        )
                        self.assertIsInstance(result, CommandViewResult)
                        return result.view

                    if human_count < 4:
                        execute_label(
                            sessions[0], "Fill Open Seats With Bots"
                        )
                    for session in sessions:
                        execute_label(session, "Ready")
                    started = execute_label(sessions[0], "Start Match")

                    self.assertEqual(started.status, RoomStatus.IN_MATCH)
                    self.assertEqual(started.game.status, MatchStatus.ACTIVE)  # type: ignore[union-attr]
                    self.assertEqual(str(started.game.dealer_seat_id), "seat-0")  # type: ignore[union-attr]
                    self.assertEqual(started.game.phase.type, "awaitingDiscard")  # type: ignore[union-attr]
                    self.assertEqual(len(started.actions), 14)
                    self.assertEqual(
                        [
                            action.presentation_index
                            for action in started.actions
                            if action.presentation_slot == "concealedTile"
                        ],
                        list(range(13)),
                    )
                    self.assertEqual(
                        sum(
                            action.presentation_slot == "drawnTile"
                            for action in started.actions
                        ),
                        1,
                    )

                    persisted = repository.load_room()
                    self.assertIsNotNone(persisted)
                    controllers = [
                        seat.controller.type for seat in persisted.seats  # type: ignore[union-attr]
                    ]
                    self.assertEqual(controllers.count("external"), human_count)
                    self.assertEqual(controllers.count("automated"), 4 - human_count)

                    for index, session in enumerate(sessions):
                        view = service.authenticated_view(session.player_token)
                        own = next(seat for seat in view.seats if seat.view == "self")
                        self.assertEqual(len(own.concealed_tiles), 13)
                        self.assertEqual(own.drawn_tile is not None, index == 0)
                        self.assertEqual(len(view.actions), 14 if index == 0 else 0)
                        self.assertNotIn("tileId", view.canonical_json())

                    reconstructed = RoomOrchestrator(
                        repository,
                        clock=MutableClock(1_000),
                        credential_source=DeterministicCapabilities(),
                        id_source=DeterministicIds(),
                        random_source=ZeroRandomSource(),
                    )
                    rebuilt = reconstructed.authenticated_view(
                        sessions[0].player_token
                    )
                    self.assertEqual(
                        [action.action_id for action in rebuilt.actions],
                        [action.action_id for action in started.actions],
                    )
                finally:
                    connection.close()

    def test_duplicate_faces_keep_distinct_positional_opaque_actions(self) -> None:
        service = RoomOrchestrator(
            self.repository,
            clock=self.clock,
            credential_source=self.credentials,
            id_source=self.ids,
            random_source=DuplicateFaceRandomSource(),
        )
        created = service.create_room(ROOM_ID, "Host")
        service.player_connected(created.player_id, 0, now_ms=1_000)
        connected = service.authenticated_view(created.player_token)
        start = next(
            action
            for action in connected.actions
            if action.label == "Start Against Bots"
        )
        started = service.execute_command(
            created.player_token,
            "duplicate-start",
            0,
            start.action_id,
        )
        self.assertIsInstance(started, CommandViewResult)

        persisted = self.repository.load_room()
        self.assertIsNotNone(persisted)
        hand = persisted.match.current_hand  # type: ignore[union-attr]
        own_hand = next(
            item for item in hand.player_hands if str(item.seat_id) == "seat-0"
        )
        duplicate_indices = [
            index
            for index, tile in enumerate(own_hand.concealed_tiles)
            if tile.face == own_hand.concealed_tiles[0].face
        ]
        self.assertGreaterEqual(len(duplicate_indices), 2)
        first_index, second_index = duplicate_indices[:2]
        descriptors = {
            action.presentation_index: action
            for action in started.view.actions
            if action.presentation_slot == "concealedTile"
        }
        first = descriptors[first_index]
        second = descriptors[second_index]
        self.assertEqual(first.label, second.label)
        self.assertNotEqual(first.action_id, second.action_id)
        self.assertNotIn(str(own_hand.concealed_tiles[first_index].tile_id), first.canonical_json())
        expected_tile_id = own_hand.concealed_tiles[second_index].tile_id

        discarded = service.execute_command(
            created.player_token,
            "duplicate-discard",
            started.view.revision,
            second.action_id,
        )
        self.assertIsInstance(discarded, CommandViewResult)
        after = self.repository.load_room()
        self.assertEqual(
            after.match.current_hand.discards[-1].tile.tile_id,  # type: ignore[union-attr]
            expected_tile_id,
        )
        self.assertNotIn("tileId", discarded.view.canonical_json())

    def test_start_is_one_revision_reconstructible_and_private(self) -> None:
        created, result = self.start_preview()
        view = result.view

        self.assertEqual(view.revision, 1)
        self.assertEqual(view.status, RoomStatus.IN_MATCH)
        self.assertEqual(view.ruleset_version, "0.2.0")
        self.assertEqual(view.state_schema_version, 3)
        self.assertEqual(
            view.capabilities,
            (
                "multiplayerLobby",
                "roomEvents",
                "hibernatingWebSockets",
                "drawDiscard",
                "bonusTiles",
                "discardWindow",
            ),
        )
        self.assertEqual(view.game.status, MatchStatus.ACTIVE)  # type: ignore[union-attr]
        self.assertEqual(str(view.game.dealer_seat_id), "seat-0")  # type: ignore[union-attr]
        self.assertEqual(view.game.phase.type, "awaitingDiscard")  # type: ignore[union-attr]
        self.assertEqual(len(view.actions), 14)
        concealed = [
            action
            for action in view.actions
            if action.presentation_slot == "concealedTile"
        ]
        self.assertEqual(
            [action.presentation_index for action in concealed], list(range(13))
        )
        drawn = action_for_slot(view, "drawnTile")
        self.assertIsNone(drawn.presentation_index)

        own = next(seat for seat in view.seats if seat.view == "self")
        self.assertEqual(len(own.concealed_tiles), 13)
        self.assertIsNotNone(own.drawn_tile)
        self.assertFalse(hasattr(own.concealed_tiles[0], "tile_id"))
        persisted = self.repository.load_room()
        self.assertIsNotNone(persisted)
        hand = persisted.match.current_hand  # type: ignore[union-attr]
        private_id = str(hand.player_hands[0].drawn_tile.tile_id)  # type: ignore[union-attr]
        public_json = view.canonical_json()
        self.assertNotIn(private_id, public_json)
        self.assertNotIn("tileId", public_json)
        self.assertIn(private_id, persisted.canonical_json())  # type: ignore[union-attr]

        reconstructed = RoomOrchestrator(
            self.repository,
            clock=self.clock,
            credential_source=self.credentials,
            id_source=self.ids,
            random_source=ZeroRandomSource(),
        )
        self.assertEqual(reconstructed.load_room(), persisted)
        rebuilt_view = reconstructed.authenticated_view(created.player_token)
        self.assertEqual(
            [action.action_id for action in rebuilt_view.actions],
            [action.action_id for action in view.actions],
        )

        self.assertTrue(
            self.service.player_disconnected(
                created.player_id,
                0,
                now_ms=1_100,
            )
        )
        offline = self.service.authenticated_view(created.player_token)
        self.assertEqual(len(offline.actions), 14)
        self.assertEqual(offline.players[0].connection_status, "DISCONNECTED")
        self.assertIsNone(offline.players[0].disconnect_expires_at_ms)

        event_json = json.dumps(
            self.connection.execute(
                "SELECT event_type, event_json FROM events ORDER BY public_sequence"
            ).fetchall()
        )
        self.assertIn("handStarted", event_json)
        self.assertNotIn("tileDrawn", event_json)
        self.assertNotIn("tileId", event_json)

    def test_deadline_boundary_bot_pump_idempotency_and_immutability(self) -> None:
        created, started = self.start_preview()
        action, discarded = self.discard_drawn_tile(created, started.view)
        first = discarded.view

        self.assertEqual(first.revision, 2)
        self.assertEqual(first.deadline_ms, 4_000)
        self.assertIsNotNone(first.window_id)
        self.assertEqual(first.game.phase.type, "discardClaims")  # type: ignore[union-attr]
        self.assertEqual(len(first.game.discards), 1)  # type: ignore[union-attr]
        self.assertEqual(first.actions, ())
        self.assertEqual(self.service.next_alarm_ms(), 4_000)

        before = self.at(3_999).authenticated_view(created.player_token)
        self.assertEqual(before.revision, 2)
        self.assertEqual(before.deadline_ms, 4_000)

        exact = self.at(4_000).authenticated_view(created.player_token)
        self.assertEqual(exact.revision, 3)
        self.assertEqual(exact.deadline_ms, 7_000)
        self.assertEqual(len(exact.game.discards), 2)  # type: ignore[union-attr]
        self.assertEqual(exact.game.phase.type, "discardClaims")  # type: ignore[union-attr]
        self.assertEqual(self.service.next_alarm_ms(), 7_000)
        self.assertFalse(self.service.advance_due(4_000))

        replay = self.service.execute_command(
            created.player_token,
            "discard-one",
            1,
            action.action_id,
        )
        self.assertEqual(replay.canonical_json(), discarded.canonical_json())
        self.assertEqual(self.repository.load_room().revision, 3)  # type: ignore[union-attr]
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM processed_commands WHERE command_id = 'discard-one'"
            ).fetchone(),
            (1,),
        )

        with self.assertRaises(RoomServiceError) as reused:
            self.service.execute_command(
                created.player_token,
                "discard-one",
                2,
                action.action_id,
            )
        self.assertEqual(reused.exception.code, "commandIdReused")

        state = self.repository.load_room()
        self.assertIsNotNone(state)
        deadline = state.pending_deadline  # type: ignore[union-attr]
        changed = state.model_copy(  # type: ignore[union-attr]
            update={
                "revision": state.revision + 1,  # type: ignore[union-attr]
                "updated_at_ms": 4_001,
                "pending_deadline": PendingDeadline(
                    window_id=deadline.window_id,
                    deadline_ms=deadline.deadline_ms + 1,
                ),
            }
        )
        with self.assertRaisesRegex(ValueError, "deadline is immutable"):
            self.repository.compare_and_swap(state.revision, changed)  # type: ignore[union-attr]

    def test_authentication_precedes_deadline_catch_up(self) -> None:
        created, started = self.start_preview()
        self.discard_drawn_tile(created, started.view)
        self.at(4_000)

        with self.assertRaises(RoomServiceError) as rejected:
            self.service.authenticated_view("invalid-player-token")
        self.assertEqual(rejected.exception.code, "invalidPlayerToken")
        self.assertEqual(self.repository.load_room().revision, 2)  # type: ignore[union-attr]

        advanced = self.service.authenticated_view(created.player_token)
        self.assertEqual(advanced.revision, 3)

    def test_preview_runs_to_one_persisted_tie(self) -> None:
        created, started = self.start_preview()
        view = started.view
        command_number = 0
        for _ in range(200):
            if view.status is RoomStatus.FINISHED:
                break
            if view.actions:
                action = next(
                    (
                        item
                        for item in view.actions
                        if item.presentation_slot == "drawnTile"
                    ),
                    view.actions[0],
                )
                command_number += 1
                result = self.service.execute_command(
                    created.player_token,
                    f"discard-{command_number}",
                    view.revision,
                    action.action_id,
                )
                view = result.view
                continue
            self.assertIsNotNone(view.deadline_ms)
            view = self.at(view.deadline_ms).authenticated_view(
                created.player_token
            )
        else:  # pragma: no cover - guard against a non-monotonic pump
            self.fail("preview did not terminate within its finite wall bound")

        self.assertEqual(view.status, RoomStatus.FINISHED)
        self.assertEqual(view.game.status, MatchStatus.FINISHED)  # type: ignore[union-attr]
        self.assertEqual(view.game.phase.type, "complete")  # type: ignore[union-attr]
        self.assertIsNone(view.deadline_ms)
        state = self.repository.load_room()
        self.assertIsNotNone(state)
        self.assertEqual(len(state.match.hand_history), 1)  # type: ignore[union-attr]
        self.assertEqual(state.match.result.reason, "LIVE_WALL_EXHAUSTED")  # type: ignore[union-attr]
        tied = [
            event
            for event in self.service.projected_events(created.player_token).events
            if event.type == "previewTied"
        ]
        self.assertEqual(len(tied), 1)
        self.assertEqual(
            tied[0].payload,
            {"outcome": "TIE", "reason": "LIVE_WALL_EXHAUSTED"},
        )


if __name__ == "__main__":
    unittest.main()
