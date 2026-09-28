from __future__ import annotations

import sqlite3
import unittest

from app.room import RoomOrchestrator, RoomServiceError
from app.persistence import RoomRepository
from app.game import DiscardClaimsPhase, SingaporeGameEngine, SeatId
from test_room_gameplay import MutableClock, DeterministicCapabilities, DeterministicIds
from test_game_claims import ArrangedDeck


class MultiplayerClaimTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.repository = RoomRepository.from_sqlite(self.connection)
        self.repository.initialize_schema(applied_at_ms=0)
        self.clock = MutableClock(1000)
        self.rng = ArrangedDeck()
        self.service = RoomOrchestrator(
            self.repository,
            clock=self.clock,
            credential_source=DeterministicCapabilities(),
            id_source=DeterministicIds(),
            random_source=self.rng,
        )
        self.command = 0

    def execute(self, session, label):
        view = self.service.authenticated_view(session.player_token)
        action = next(a for a in view.actions if a.label == label)
        self.command += 1
        return self.service.execute_command(
            session.player_token, f"cmd-{self.command}", view.revision, action.action_id
        )

    def start(self, humans=4):
        host = self.service.create_room("ab" * 32, "Host")
        self.sessions = [host]
        for i in range(1, humans):
            self.sessions.append(
                self.service.join_room(host.invite_token, f"Human {i}")
            )
        for s in self.sessions:
            self.service.player_connected(s.player_id, 0, now_ms=1000)
        if humans < 4:
            self.execute(host, "Fill Open Seats With Bots")
        for s in self.sessions:
            self.execute(s, "Ready")
        self.execute(host, "Start Match")
        view = self.service.authenticated_view(host.player_token)
        action = next(a for a in view.actions if a.presentation_slot == "drawnTile")
        self.service.execute_command(
            host.player_token, "discard", view.revision, action.action_id
        )
        return [self.service.authenticated_view(s.player_token) for s in self.sessions]

    def test_simultaneous_claims_reconnect_replay_and_deadline(self):
        views = self.start()
        self.assertEqual(views[1].deadline_ms, 4000)
        chow = next(a for a in views[1].actions if a.label == "Chow")
        pong = next(a for a in views[2].actions if a.label == "Pong")
        revision = views[1].revision
        self.clock.timestamp_ms = 3999
        accepted = self.service.execute_command(
            self.sessions[2].player_token, "pong", revision, pong.action_id
        )
        self.assertTrue(accepted.view.game.own_claim_submitted)
        self.assertEqual(accepted.view.deadline_ms, 4000)
        # Fresh orchestrator reconstructs the response and the independent catalogue.
        self.service = RoomOrchestrator(
            self.repository, clock=self.clock, random_source=self.rng
        )
        refreshed = self.service.authenticated_view(self.sessions[1].player_token)
        self.assertEqual(
            [a.action_id for a in refreshed.actions],
            [a.action_id for a in views[1].actions],
        )
        self.assertFalse(refreshed.game.own_claim_submitted)
        self.service.execute_command(
            self.sessions[1].player_token, "chow", revision, chow.action_id
        )
        self.assertEqual(
            self.repository.load_room()
            .match.current_hand.discards[-1]
            .claimed_by_seat_id,
            None,
        )
        with self.assertRaises(RoomServiceError):
            self.service.execute_command(
                self.sessions[2].player_token,
                "different-choice",
                revision,
                pong.action_id,
            )
        self.clock.timestamp_ms = 4000
        self.assertTrue(self.service.advance_due())
        self.assertFalse(self.service.advance_due())
        final = self.repository.load_room()
        self.assertEqual(
            final.match.current_hand.discards[-1].claimed_by_seat_id,
            final.seats[2].seat_id,
        )
        self.assertEqual(len(final.match.current_hand.player_hands[2].melds), 1)
        replay = self.service.execute_command(
            self.sessions[2].player_token, "pong", revision, pong.action_id
        )
        self.assertEqual(replay.canonical_json(), accepted.canonical_json())
        rows = self.connection.execute("SELECT event_json FROM events").fetchall()
        encoded = str(rows)
        self.assertNotIn("claimSubmitted", encoded)
        self.assertNotIn("tileId", encoded)
        self.assertIn("claimResolved", encoded)
        self.assertIn("meldDeclared", encoded)
        projected = self.service.projected_events(
            self.sessions[0].player_token, after_sequence=0
        )
        meld_event = next(e for e in projected.events if e.type == "meldDeclared")
        self.assertEqual(len(meld_event.payload["tiles"]), 3)
        self.assertNotIn("tileId", projected.canonical_json())

    def test_exact_deadline_rejects_and_no_claims_wait(self):
        views = self.start()
        action = next(a for a in views[2].actions if a.label == "Pong")
        self.clock.timestamp_ms = 3999
        self.assertFalse(self.service.advance_due())
        self.clock.timestamp_ms = 4000
        with self.assertRaises(RoomServiceError):
            self.service.execute_command(
                self.sessions[2].player_token,
                "late",
                views[2].revision,
                action.action_id,
            )
        hand = self.repository.load_room().match.current_hand
        self.assertIsNone(hand.discards[-1].claimed_by_seat_id)
        self.assertFalse(isinstance(hand.phase, DiscardClaimsPhase))

    def test_all_passes_keep_original_deadline(self):
        views = self.start()
        for index in (1, 2):
            action = next(a for a in views[index].actions if a.label == "Pass")
            self.service.execute_command(
                self.sessions[index].player_token,
                f"pass-{index}",
                views[index].revision,
                action.action_id,
            )
        state = self.repository.load_room()
        self.assertEqual(state.pending_deadline.deadline_ms, 4000)
        self.assertIsInstance(state.match.current_hand.phase, DiscardClaimsPhase)
        self.assertFalse(self.service.advance_due(3999))
        self.assertTrue(self.service.advance_due(4000))

    def test_bot_pong_is_committed_at_opening_and_beats_human_chow(self):
        views = self.start(humans=2)
        state = self.repository.load_room()
        self.assertTrue(
            any(
                c.seat_id == state.seats[2].seat_id and c.kind.value == "PONG"
                for c in state.match.current_hand.pending_claims
            )
        )
        self.assertFalse(views[1].game.own_claim_submitted)
        self.execute(self.sessions[1], "Chow")
        self.service = RoomOrchestrator(
            self.repository, clock=self.clock, random_source=self.rng
        )
        self.assertTrue(self.service.advance_due(4000))
        self.assertEqual(
            self.repository.load_room()
            .match.current_hand.discards[0]
            .claimed_by_seat_id,
            state.seats[2].seat_id,
        )
