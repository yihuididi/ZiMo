"""Revisioned settings and reconstructed Kong-4 windows through the room boundary."""
import unittest

from app.game import GameConfig, SingaporeGameEngine, RoomStatus
from app.room import RoomOrchestrator, RoomServiceError
import test_room_claims
from test_game_variations import WondersDeck


class RoomVariationTests(unittest.TestCase):
    setUp = test_room_claims.MultiplayerClaimTests.setUp
    execute = test_room_claims.MultiplayerClaimTests.execute

    def start_variation_room(self):
        self.service._game_engine = SingaporeGameEngine(WondersDeck())
        host = self.service.create_room("ab" * 32,"Host")
        self.sessions = [host] + [self.service.join_room(host.invite_token,f"Human {i}") for i in range(1,4)]
        view = self.service.authenticated_view(host.player_token)
        self.service.update_config(host.player_token,view.revision,GameConfig(kong_four_robbery_enabled=True).canonical_json())
        for session in self.sessions:
            self.service.player_connected(session.player_id,0,now_ms=1000)
            self.execute(session,"Ready")
        return host

    def test_ready_room_rejects_edits_until_host_unreadies(self):
        host = self.start_variation_room()
        ready = self.service.authenticated_view(host.player_token)
        self.assertEqual(ready.status,RoomStatus.READY)
        with self.assertRaises(RoomServiceError):
            self.service.update_config(host.player_token,ready.revision,GameConfig(seven_pairs_enabled=True).canonical_json())
        self.execute(host,"Unready")
        view = self.service.authenticated_view(host.player_token)
        result = self.service.update_config(host.player_token,view.revision,GameConfig(seven_pairs_enabled=True).canonical_json())
        self.assertTrue(result.view.config.seven_pairs_enabled)
        self.assertTrue(all(not p.ready for p in result.view.players))

    def test_robbery_reconnect_idempotency_and_exact_deadline(self):
        host = self.start_variation_room()
        self.execute(host,"Start Match")
        self.execute(host,"Kong-4")
        claimant = self.sessions[1]
        view = self.service.authenticated_view(claimant.player_token)
        self.assertEqual(view.game.phase.kong_kind,"KONG_4")
        self.assertEqual(view.deadline_ms,4000)
        action = next(a for a in view.actions if a.label=="Game")
        self.clock.timestamp_ms = 3999
        self.service = RoomOrchestrator(self.repository,clock=self.clock)
        replayed = self.service.authenticated_view(claimant.player_token)
        self.assertEqual(replayed.deadline_ms,view.deadline_ms)
        self.assertEqual(replayed.window_id,view.window_id)
        self.service.execute_command(claimant.player_token,"rob",view.revision,action.action_id)
        self.service.execute_command(claimant.player_token,"rob",view.revision,action.action_id)
        self.assertEqual(self.service.authenticated_view(host.player_token).game.phase.type,"kongRobbery")
        self.clock.timestamp_ms = 4000
        self.service.advance_due(4000)
        final = self.service.authenticated_view(host.player_token)
        self.assertEqual(final.game.result.reason,"THIRTEEN_WONDERS")
        ledger = final.game.payments
        self.service.advance_due(4000)
        self.assertEqual(self.service.authenticated_view(host.player_token).game.payments,ledger)
        with self.assertRaises(RoomServiceError):
            self.service.execute_command(claimant.player_token,"late-rob",view.revision,action.action_id)
