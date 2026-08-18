from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import unittest

from app.game import FixedClock, GameConfig, MatchStatus, RoomStatus
from app.persistence import RoomRepository
from app.room import (
    CommandViewResult,
    RoomOrchestrator,
    RoomServiceError,
    SessionEndedResult,
)


ROOM_ID = "0123456789abcdef" * 4
ROTATION_DOMAIN = b"zimo:invite-rotation:v1\x00"


class DeterministicCapabilities:
    def __init__(self) -> None:
        self.count = 0
        self.issued: list[str] = []

    def __call__(self) -> str:
        self.count += 1
        value = base64.urlsafe_b64encode(bytes([self.count]) * 32).decode().rstrip("=")
        self.issued.append(value)
        return value


class DeterministicIds:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def __call__(self, prefix: str) -> str:
        count = self.counts.get(prefix, 0) + 1
        self.counts[prefix] = count
        return f"{prefix}-{count}"


def descriptor_id(view, label: str) -> str:
    return next(action.action_id for action in view.actions if action.label == label)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class RoomOrchestratorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.repository = RoomRepository.from_sqlite(self.connection)
        self.repository.initialize_schema(applied_at_ms=900)
        self.capabilities = DeterministicCapabilities()
        self.ids = DeterministicIds()
        self.service = self.service_at(1_000)

    def tearDown(self) -> None:
        self.connection.close()

    def service_at(self, timestamp_ms: int) -> RoomOrchestrator:
        return RoomOrchestrator(
            self.repository,
            clock=FixedClock(timestamp_ms),
            credential_source=self.capabilities,
            id_source=self.ids,
        )

    def create(self, display_name: str = "Host"):
        return self.service.create_room(ROOM_ID, display_name)

    def assert_service_error(
        self,
        expected_status: int,
        expected_code: str,
        callback,
        *,
        current_revision: int | None = None,
    ) -> RoomServiceError:
        with self.assertRaises(RoomServiceError) as caught:
            callback()
        error = caught.exception
        self.assertEqual(error.status_code, expected_status)
        self.assertEqual(error.code, expected_code)
        if current_revision is not None:
            self.assertEqual(error.current_revision, current_revision)
        return error


class RoomCreationAndAuthenticationTests(RoomOrchestratorTestCase):
    def test_create_join_authenticate_hashes_secrets_and_assigns_lowest_seat(self) -> None:
        created = self.create("  Ｈost   Player  ")
        player_token = created.player_token
        invite_token = created.invite_token

        self.assertEqual(created.room_id, ROOM_ID)
        self.assertEqual(created.player_id, "player-1")
        self.assertEqual(created.view.revision, 0)
        self.assertEqual(created.view.status, RoomStatus.WAITING_FOR_PLAYERS)
        self.assertEqual(created.view.players[0].display_name, "Host Player")
        self.assertEqual(created.view.seats[0].slot, 0)
        self.assertEqual(str(created.view.viewer_player_id), created.player_id)
        self.assertEqual(
            created.view.capabilities,
            ("multiplayerLobby", "roomEvents", "hibernatingWebSockets"),
        )

        player_row = self.connection.execute(
            "SELECT token_hash FROM players WHERE player_id = ?",
            (created.player_id,),
        ).fetchone()
        invite_row = self.connection.execute(
            "SELECT invite_token_hash, invite_generation FROM room_credentials"
        ).fetchone()
        self.assertEqual(player_row, (sha256(player_token),))
        self.assertEqual(invite_row, (sha256(invite_token), 0))
        dump = "\n".join(self.connection.iterdump())
        self.assertNotIn(player_token, dump)
        self.assertNotIn(invite_token, dump)

        authenticated = self.service.authenticated_view(player_token)
        self.assertEqual(str(authenticated.viewer_player_id), created.player_id)
        self.assert_service_error(
            401,
            "invalidPlayerToken",
            lambda: self.service.authenticated_view("not-a-player-token"),
        )

        self.assert_service_error(
            403,
            "invalidInviteToken",
            lambda: self.service.join_room("not-an-invite", "Member"),
        )
        self.assertEqual(self.repository.load_room().revision, 0)  # type: ignore[union-attr]

        joined = self.service.join_room(invite_token, "Member")
        self.assertEqual(joined.player_id, "player-2")
        self.assertEqual(joined.view.revision, 1)
        own_seat = next(
            seat
            for seat in joined.view.seats
            if seat.view == "self"
        )
        self.assertEqual(own_seat.slot, 1)
        self.assertEqual(
            str(self.service.authenticated_view(joined.player_token).viewer_player_id),
            joined.player_id,
        )
        self.assertNotIn(joined.player_token, "\n".join(self.connection.iterdump()))

        self.assert_service_error(
            409,
            "displayNameTaken",
            lambda: self.service.join_room(invite_token, "member"),
            current_revision=1,
        )

    def test_cache_is_non_authoritative_and_a_new_orchestrator_reconstructs(self) -> None:
        created = self.create()
        reconstructed = self.service_at(1_100)
        self.assertIsNone(reconstructed.cached_state)
        self.assertTrue(reconstructed.player_connected(created.player_id, 0))

        view = reconstructed.authenticated_view(created.player_token)
        self.assertEqual(view.revision, 0)
        self.assertEqual(view.server_time_ms, 1_100)
        self.assertEqual(reconstructed.cached_state, self.repository.load_room())

        action = descriptor_id(view, "Ready")
        result = reconstructed.execute_command(
            created.player_token, "ready-after-eviction", 0, action
        )
        self.assertIsInstance(result, CommandViewResult)
        self.assertEqual(result.view.revision, 1)  # type: ignore[union-attr]


class RoomPresenceTests(RoomOrchestratorTestCase):
    def test_disconnect_projects_deadline_and_reconnect_clears_without_revision(self) -> None:
        created = self.create()
        self.assertEqual(created.view.presence_version, 1)
        self.assertEqual(created.view.players[0].connection_status, "DISCONNECTED")
        self.assertEqual(
            created.view.players[0].disconnect_expires_at_ms, 301_000
        )

        self.assertTrue(self.service.player_connected(created.player_id, 0))

        disconnected = self.service_at(2_000)
        self.assertTrue(disconnected.player_disconnected(created.player_id, 0))
        self.assertFalse(
            self.service_at(3_000).player_disconnected(created.player_id, 0)
        )
        view = disconnected.authenticated_view(created.player_token)
        self.assertEqual(view.revision, 0)
        self.assertEqual(view.presence_version, 3)
        self.assertEqual(view.players[0].connection_status, "DISCONNECTED")
        self.assertEqual(view.players[0].disconnect_expires_at_ms, 302_000)
        self.assertEqual(disconnected.next_presence_alarm_ms(), 302_000)

        self.assertFalse(disconnected.player_connected(created.player_id, 1))
        self.assertTrue(disconnected.player_connected(created.player_id, 0))
        reconnected = disconnected.authenticated_view(created.player_token)
        self.assertEqual(reconnected.revision, 0)
        self.assertEqual(reconnected.presence_version, 4)
        self.assertEqual(reconnected.players[0].connection_status, "CONNECTED")
        self.assertIsNone(reconnected.players[0].disconnect_expires_at_ms)
        self.assertIsNone(disconnected.next_presence_alarm_ms())

    def test_due_host_is_removed_revoked_and_transfers_host_permission(self) -> None:
        created = self.create()
        member = self.service_at(1_100).join_room(created.invite_token, "Member")
        self.assertTrue(self.service.player_connected(member.player_id, 0))

        expired = self.service_at(301_000).expire_disconnected_players(())
        self.assertEqual(expired, (created.player_id,))
        state = self.repository.load_room()
        self.assertIsNotNone(state)
        self.assertEqual(state.revision, 3)  # type: ignore[union-attr]
        self.assertEqual(len(state.players), 1)  # type: ignore[union-attr]
        self.assertEqual(str(state.players[0].player_id), member.player_id)  # type: ignore[union-attr]
        self.assertEqual(state.players[0].role.value, "HOST")  # type: ignore[union-attr]
        self.assertIsNone(self.service.next_presence_alarm_ms())
        self.assert_service_error(
            401,
            "invalidPlayerToken",
            lambda: self.service.authenticated_view(created.player_token),
        )
        promoted_view = self.service.authenticated_view(member.player_token)
        self.assertEqual(promoted_view.presence_version, 4)
        self.assertTrue(
            any(
                action.label == "Create New Invitation Link"
                for action in promoted_view.actions
            )
        )

    def test_alarm_reconciles_live_identity_and_multiple_due_players(self) -> None:
        created = self.create()
        first = self.service_at(1_100).join_room(created.invite_token, "First")
        second = self.service_at(1_200).join_room(created.invite_token, "Second")
        self.assertTrue(self.service.player_connected(second.player_id, 0))

        live_alarm = self.service_at(301_100)
        expired = live_alarm.expire_disconnected_players(
            ((created.player_id, 0), (second.player_id, 0))
        )
        self.assertEqual(expired, (first.player_id,))
        state = self.repository.load_room()
        self.assertEqual(state.revision, 4)  # type: ignore[union-attr]
        self.assertEqual(
            {str(player.player_id) for player in state.players},  # type: ignore[union-attr]
            {created.player_id, second.player_id},
        )
        view = live_alarm.authenticated_view(created.player_token)
        self.assertEqual(view.presence_version, 6)
        self.assertTrue(
            all(player.connection_status == "CONNECTED" for player in view.players)
        )

    def test_in_match_disconnect_has_no_deadline_and_never_expires(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        start_id = descriptor_id(created.view, "Start Against Bots")
        result = self.service.execute_command(
            created.player_token, "start", 0, start_id
        )
        self.assertEqual(result.view.status, RoomStatus.IN_MATCH)  # type: ignore[union-attr]

        in_match = self.service_at(2_000)
        self.assertTrue(in_match.player_disconnected(created.player_id, 0))
        view = in_match.authenticated_view(created.player_token)
        player = next(
            item for item in view.players if str(item.player_id) == created.player_id
        )
        self.assertEqual(player.connection_status, "DISCONNECTED")
        self.assertIsNone(player.disconnect_expires_at_ms)
        self.assertIsNone(in_match.next_presence_alarm_ms())
        self.assertEqual(
            self.service_at(1_000_000).expire_disconnected_players(()), ()
        )
        self.assertEqual(self.repository.load_room().revision, 1)  # type: ignore[union-attr]

    def test_finished_room_still_projects_disconnect_without_eviction(self) -> None:
        created = self.create()
        self.assertTrue(self.service.player_connected(created.player_id, 0))
        state = self.repository.load_room()
        self.assertIsNotNone(state)
        finished = state.model_copy(  # type: ignore[union-attr]
            update={
                "revision": 1,
                "status": RoomStatus.FINISHED,
                "updated_at_ms": 1_100,
            }
        )
        self.service.commit_room(finished, expected_revision=0)

        completed = self.service_at(2_000)
        self.assertTrue(completed.player_disconnected(created.player_id, 0))
        view = completed.authenticated_view(created.player_token)
        self.assertEqual(view.status, RoomStatus.FINISHED)
        self.assertEqual(view.players[0].connection_status, "DISCONNECTED")
        self.assertIsNone(view.players[0].disconnect_expires_at_ms)
        self.assertIsNone(completed.next_presence_alarm_ms())
        self.assertEqual(
            self.service_at(1_000_000).expire_disconnected_players(()), ()
        )
        self.assertEqual(self.repository.load_room().revision, 1)  # type: ignore[union-attr]

    def test_player_without_a_first_socket_is_expired_after_grace_period(self) -> None:
        created = self.create()
        self.assertEqual(created.view.players[0].connection_status, "DISCONNECTED")
        self.assertEqual(self.service.next_presence_alarm_ms(), 301_000)

        self.assertEqual(
            self.service_at(301_000).expire_disconnected_players(()),
            (created.player_id,),
        )
        state = self.repository.load_room()
        self.assertEqual(state.status, RoomStatus.FINISHED)  # type: ignore[union-attr]
        self.assertEqual(state.revision, 1)  # type: ignore[union-attr]
        self.assert_service_error(
            401,
            "invalidPlayerToken",
            lambda: self.service.authenticated_view(created.player_token),
        )

    def test_ready_member_disconnect_is_one_atomic_revision_and_is_idempotent(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        member = self.service_at(1_100).join_room(created.invite_token, "Member")
        self.service.reconcile_socket_presence(
            ((created.player_id, 0), (member.player_id, 0))
        )
        member_view = self.service.authenticated_view(member.player_token)
        ready_id = descriptor_id(member_view, "Ready")
        ready = self.service_at(1_200).execute_command(
            member.player_token,
            "member-ready",
            member_view.revision,
            ready_id,
        )
        self.assertTrue(
            next(
                player
                for player in ready.view.players  # type: ignore[union-attr]
                if str(player.player_id) == member.player_id
            ).ready
        )

        disconnected = self.service_at(1_300)
        self.assertTrue(
            disconnected.player_disconnected(
                member.player_id,
                0,
                ((created.player_id, 0),),
            )
        )
        state = self.repository.load_room()
        self.assertEqual(state.revision, 3)  # type: ignore[union-attr]
        member_state = next(  # type: ignore[union-attr]
            player for player in state.players if str(player.player_id) == member.player_id
        )
        self.assertFalse(member_state.ready)
        presence = self.repository.list_player_presence()
        self.assertEqual(
            [(item.player_id, item.disconnect_expires_at_ms) for item in presence],
            [(member.player_id, 301_300)],
        )
        last_event = self.repository.list_events()[-1]
        self.assertEqual(last_event.event_type, "playerReadinessChanged")
        self.assertEqual(last_event.revision, 3)
        version = self.repository.presence_version()

        self.assertFalse(
            self.service_at(1_400).player_disconnected(
                member.player_id,
                0,
                ((created.player_id, 0),),
            )
        )
        self.assertEqual(self.repository.load_room().revision, 3)  # type: ignore[union-attr]
        self.assertEqual(self.repository.presence_version(), version)

    def test_ready_host_disconnect_resets_ready_and_transfers_in_one_revision(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        first = self.service_at(1_100).join_room(created.invite_token, "First")
        second = self.service_at(1_100).join_room(created.invite_token, "Second")
        self.service.reconcile_socket_presence(
            (
                (created.player_id, 0),
                (second.player_id, 0),
                (first.player_id, 0),
            )
        )
        host_view = self.service.authenticated_view(created.player_token)
        ready_id = descriptor_id(host_view, "Ready")
        self.service_at(1_200).execute_command(
            created.player_token,
            "host-ready",
            host_view.revision,
            ready_id,
        )

        self.assertTrue(
            self.service_at(1_300).player_disconnected(
                created.player_id,
                0,
                ((second.player_id, 0), (first.player_id, 0)),
            )
        )
        state = self.repository.load_room()
        self.assertEqual(state.revision, 4)  # type: ignore[union-attr]
        players = {str(player.player_id): player for player in state.players}  # type: ignore[union-attr]
        self.assertFalse(players[created.player_id].ready)
        self.assertEqual(players[created.player_id].role.value, "MEMBER")
        self.assertEqual(players[first.player_id].role.value, "HOST")
        events = self.repository.list_events()
        self.assertEqual(
            [(event.event_type, event.revision) for event in events[-2:]],
            [("playerReadinessChanged", 4), ("hostTransferred", 4)],
        )

    def test_batch_reconnect_transfers_waiting_host_by_join_order_not_input_order(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        first = self.service_at(1_100).join_room(created.invite_token, "First")
        second = self.service_at(1_200).join_room(created.invite_token, "Second")
        self.assertTrue(
            self.service_at(1_300).player_disconnected(
                created.player_id,
                0,
                (),
            )
        )
        self.assertEqual(self.repository.load_room().revision, 2)  # type: ignore[union-attr]

        self.assertTrue(
            self.service_at(1_400).reconcile_socket_presence(
                ((second.player_id, 0), (first.player_id, 0))
            )
        )
        state = self.repository.load_room()
        self.assertEqual(state.revision, 3)  # type: ignore[union-attr]
        host = next(  # type: ignore[union-attr]
            player for player in state.players if player.role.value == "HOST"
        )
        self.assertEqual(str(host.player_id), first.player_id)
        self.assertEqual(
            {item.player_id for item in self.repository.list_player_presence()},
            {created.player_id},
        )

    def test_offline_player_cannot_reuse_ready_or_start_action_ids(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        connected = self.service.authenticated_view(created.player_token)
        ready_id = descriptor_id(connected, "Ready")
        start_id = descriptor_id(connected, "Start Against Bots")
        self.assertTrue(
            self.service_at(1_100).player_disconnected(
                created.player_id,
                0,
                (),
            )
        )
        offline = self.service.authenticated_view(created.player_token)
        self.assertEqual(offline.revision, connected.revision)
        by_label = {action.label: action for action in offline.actions}
        self.assertFalse(by_label["Ready"].enabled)
        self.assertFalse(by_label["Start Against Bots"].enabled)
        version = offline.presence_version

        for command_id, action_id in (
            ("offline-ready", ready_id),
            ("offline-start", start_id),
        ):
            self.assert_service_error(
                409,
                "actionNotAvailable",
                lambda command_id=command_id, action_id=action_id: (
                    self.service.execute_command(
                        created.player_token,
                        command_id,
                        connected.revision,
                        action_id,
                    )
                ),
                current_revision=connected.revision,
            )
        self.assertEqual(self.repository.load_room().revision, connected.revision)  # type: ignore[union-attr]
        self.assertEqual(self.repository.presence_version(), version)


class RoomCommandTests(RoomOrchestratorTestCase):
    def test_rotate_invite_is_deterministic_idempotent_and_body_bound(self) -> None:
        created = self.create()
        rotate_id = descriptor_id(created.view, "Create New Invitation Link")
        command_id = "rotate-command"

        first = self.service.execute_command(
            created.player_token, command_id, 0, rotate_id
        )
        self.assertIsInstance(first, CommandViewResult)
        self.assertIsNotNone(first.invite_token)  # type: ignore[union-attr]
        rotated = first.invite_token  # type: ignore[union-attr]
        expected_digest = hmac.new(
            created.player_token.encode(),
            ROTATION_DOMAIN
            + b"\x00".join(
                value.encode()
                for value in (ROOM_ID, created.player_id, command_id)
            ),
            hashlib.sha256,
        ).digest()
        expected = base64.urlsafe_b64encode(expected_digest).decode().rstrip("=")
        self.assertEqual(rotated, expected)
        self.assertEqual(first.view.revision, 1)  # type: ignore[union-attr]

        replay = self.service.execute_command(
            created.player_token, command_id, 0, rotate_id
        )
        self.assertEqual(replay.canonical_data(), first.canonical_data())
        self.assertEqual(self.repository.load_room().revision, 1)  # type: ignore[union-attr]

        ready_id = descriptor_id(created.view, "Ready")
        self.assert_service_error(
            409,
            "commandIdReused",
            lambda: self.service.execute_command(
                created.player_token, command_id, 0, ready_id
            ),
            current_revision=1,
        )

        stored_result = self.connection.execute(
            "SELECT result_json FROM processed_commands WHERE command_id = ?",
            (command_id,),
        ).fetchone()[0]
        self.assertNotIn(rotated, stored_result)
        self.assertNotIn(created.player_token, stored_result)
        self.assertEqual(json.loads(stored_result)["rotatedInvite"], True)
        credentials = self.repository.load_room_credentials()
        self.assertEqual(credentials.invite_generation, 1)  # type: ignore[union-attr]
        self.assertEqual(credentials.invite_token_hash, sha256(rotated))  # type: ignore[union-attr]

        self.assert_service_error(
            403,
            "invalidInviteToken",
            lambda: self.service.join_room(created.invite_token, "Old Invite"),
        )
        joined = self.service.join_room(rotated, "New Invite")
        self.assertEqual(joined.view.revision, 2)
        replay_after_eviction = self.service_at(1_100).execute_command(
            created.player_token, command_id, 0, rotate_id
        )
        self.assertEqual(replay_after_eviction.canonical_data(), first.canonical_data())
        self.assertEqual(self.repository.load_room().revision, 2)  # type: ignore[union-attr]

    def test_revision_is_checked_before_catalog_resolution_and_stale_handles_fail(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        ready_id = descriptor_id(created.view, "Ready")

        self.assert_service_error(
            409,
            "revisionConflict",
            lambda: self.service.execute_command(
                created.player_token, "future", 1, "0" * 64
            ),
            current_revision=0,
        )
        result = self.service.execute_command(
            created.player_token, "ready", 0, ready_id
        )
        self.assertEqual(result.view.revision, 1)  # type: ignore[union-attr]
        self.assert_service_error(
            409,
            "actionNotAvailable",
            lambda: self.service.execute_command(
                created.player_token, "stale-handle", 1, ready_id
            ),
            current_revision=1,
        )
        self.assert_service_error(
            401,
            "invalidPlayerToken",
            lambda: self.service.execute_command(
                "bad-token", "bad-auth", 0, ready_id
            ),
        )

    def test_default_config_is_a_host_only_noop_and_other_shapes_are_rejected(self) -> None:
        created = self.create()
        initial_generation = self.service.commit_generation
        initial_events = self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        defaults = GameConfig().canonical_json()

        result = self.service.update_config(created.player_token, 0, defaults)
        self.assertEqual(result.view.revision, 0)
        self.assertEqual(self.repository.load_room().revision, 0)  # type: ignore[union-attr]
        self.assertEqual(self.service.commit_generation, initial_generation)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            initial_events,
        )

        self.assert_service_error(
            422,
            "invalidConfig",
            lambda: self.service.update_config(created.player_token, 0, "{}"),
        )
        changed = GameConfig().canonical_data()
        changed["shooterMode"] = True
        self.assert_service_error(
            422,
            "invalidConfig",
            lambda: self.service.update_config(
                created.player_token,
                0,
                json.dumps(changed, separators=(",", ":"), sort_keys=True),
            ),
            current_revision=0,
        )

        joined = self.service.join_room(created.invite_token, "Member")
        self.assert_service_error(
            403,
            "hostRequired",
            lambda: self.service.update_config(joined.player_token, 1, defaults),
            current_revision=1,
        )

    def test_leave_revokes_player_token_and_live_ticket_atomically(self) -> None:
        created = self.create()
        joined = self.service.join_room(created.invite_token, "Member")
        ticket = self.service.issue_socket_ticket(joined.player_token)
        before_revision = self.repository.load_room().revision  # type: ignore[union-attr]
        leave_id = descriptor_id(joined.view, "Leave Room")

        ended = self.service.execute_command(
            joined.player_token, "member-leave", before_revision, leave_id
        )
        self.assertIsInstance(ended, SessionEndedResult)
        self.assertEqual(ended.revision, before_revision + 1)  # type: ignore[union-attr]
        self.assert_service_error(
            401,
            "invalidPlayerToken",
            lambda: self.service.authenticated_view(joined.player_token),
        )
        self.assert_service_error(
            401,
            "invalidSocketTicket",
            lambda: self.service.consume_socket_ticket(ticket.ticket, now_ms=1_001),
        )

        record = self.repository.get_player(joined.player_id, include_revoked=True)
        self.assertIsNotNone(record)
        self.assertEqual(record.left_at_ms, 1_000)  # type: ignore[union-attr]
        self.assertEqual(record.auth_generation, 1)  # type: ignore[union-attr]
        host_view = self.service.authenticated_view(created.player_token)
        self.assertEqual([str(player.player_id) for player in host_view.players], [created.player_id])
        self.assertIsNone(host_view.seats[1].occupant)

    def test_start_against_bots_commits_one_revision_with_three_events(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        start_id = descriptor_id(created.view, "Start Against Bots")
        result = self.service.execute_command(
            created.player_token, "solo-start", 0, start_id
        )
        self.assertIsInstance(result, CommandViewResult)
        view = result.view  # type: ignore[union-attr]
        self.assertEqual(view.revision, 1)
        self.assertEqual(view.status, RoomStatus.IN_MATCH)
        self.assertEqual(view.game.status, MatchStatus.PENDING_SETUP)  # type: ignore[union-attr]
        self.assertIsNone(view.game.dealer_seat_id)  # type: ignore[union-attr]
        self.assertEqual(view.actions, ())
        self.assertEqual(
            [event.type for event in self.service.projected_events(created.player_token).events],
            ["roomCreated", "botsFilled", "playerReadinessChanged", "matchStarted"],
        )
        self.assertEqual(
            [event.revision for event in self.service.projected_events(created.player_token).events],
            [0, 1, 1, 1],
        )
        self.assert_service_error(
            409,
            "roomClosed",
            lambda: self.service.join_room(created.invite_token, "Late"),
            current_revision=1,
        )


class RoomTicketsEventsAndAtomicityTests(RoomOrchestratorTestCase):
    def test_socket_tickets_are_hashed_single_use_expiring_and_revision_free(self) -> None:
        created = self.create()
        first = self.service.issue_socket_ticket(created.player_token)
        self.assertEqual(first.expires_at_ms, 31_000)
        self.assertEqual(self.repository.load_room().revision, 0)  # type: ignore[union-attr]
        row = self.connection.execute(
            "SELECT ticket_hash, consumed_at_ms FROM socket_tickets"
        ).fetchone()
        self.assertEqual(row, (sha256(first.ticket), None))
        self.assertNotIn(first.ticket, "\n".join(self.connection.iterdump()))

        identity = self.service.consume_socket_ticket(first.ticket, now_ms=1_001)
        self.assertEqual(identity.player_id, created.player_id)
        self.assertEqual(identity.auth_generation, 0)
        self.assertEqual(self.repository.load_room().revision, 0)  # type: ignore[union-attr]
        self.assert_service_error(
            401,
            "invalidSocketTicket",
            lambda: self.service.consume_socket_ticket(first.ticket, now_ms=1_002),
        )

        second = self.service.issue_socket_ticket(created.player_token)
        self.assert_service_error(
            401,
            "invalidSocketTicket",
            lambda: self.service.consume_socket_ticket(second.ticket, now_ms=31_000),
        )
        self.assertEqual(self.repository.cleanup_socket_tickets(now_ms=31_000), 1)
        self.assertIsNone(self.repository.get_socket_ticket(sha256(second.ticket)))
        self.assertEqual(self.repository.load_room().revision, 0)  # type: ignore[union-attr]

    def test_events_are_cursor_projected_and_contain_no_credentials_or_actions(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        joined = self.service.join_room(created.invite_token, "Member")
        self.service.player_connected(joined.player_id, 0)
        ready_id = descriptor_id(joined.view, "Ready")
        self.service.execute_command(joined.player_token, "member-ready", 1, ready_id)

        projected = self.service.projected_events(created.player_token, after_sequence=1)
        self.assertEqual([event.public_sequence for event in projected.events], [2, 3])
        self.assertEqual([event.type for event in projected.events], ["playerJoined", "playerReadinessChanged"])
        self.assertEqual(projected.next_sequence, 3)
        empty = self.service.projected_events(created.player_token, after_sequence=3)
        self.assertEqual(empty.events, ())
        self.assertEqual(empty.next_sequence, 3)

        serialized = projected.canonical_json()
        database_events = json.dumps(
            self.connection.execute(
                "SELECT event_type, event_json FROM events ORDER BY public_sequence"
            ).fetchall()
        )
        for secret in (
            created.player_token,
            created.invite_token,
            joined.player_token,
            ready_id,
        ):
            self.assertNotIn(secret, serialized)
            self.assertNotIn(secret, database_events)
        for forbidden in ("tokenHash", "inviteToken", "actionId", "ticket"):
            self.assertNotIn(forbidden, serialized)
            self.assertNotIn(forbidden, database_events)

    def test_failed_event_write_rolls_back_state_player_and_command_projections(self) -> None:
        created = self.create()
        self.service.player_connected(created.player_id, 0)
        ready_id = descriptor_id(created.view, "Ready")
        self.connection.execute(
            """
            CREATE TRIGGER reject_ready_event
            BEFORE INSERT ON events
            WHEN NEW.event_type = 'playerReadinessChanged'
            BEGIN
                SELECT RAISE(ABORT, 'forced event failure');
            END
            """
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.service.execute_command(
                created.player_token, "must-roll-back", 0, ready_id
            )

        persisted = self.repository.load_room()
        self.assertEqual(persisted.revision, 0)  # type: ignore[union-attr]
        self.assertFalse(persisted.players[0].ready)  # type: ignore[union-attr]
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM processed_commands").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            1,
        )
        player = self.repository.get_player(created.player_id)
        self.assertIsNotNone(player)
        self.assertIsNone(player.left_at_ms)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
