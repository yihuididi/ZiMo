from __future__ import annotations

import re
import unittest

from app.game import (
    AutomatedSeatController,
    GameConfig,
    MatchStatus,
    PlayerId,
    PlayerRole,
    RoomStatus,
    build_public_room_view,
)
from app.lobby import (
    LobbyAction,
    LobbyActionKind,
    LobbyDomainError,
    apply_lobby_disconnect,
    apply_lobby_action,
    catalog_lobby_actions,
    create_lobby_room,
    join_lobby_room,
    normalize_display_name,
    reconcile_lobby_host,
    resolve_lobby_action,
    update_lobby_config,
)


def action(room, player_id: str, kind: LobbyActionKind) -> LobbyAction:
    return next(
        item.action
        for item in catalog_lobby_actions(room, player_id)
        if item.action.kind is kind
    )


def action_id(room, player_id: str, kind: LobbyActionKind) -> str:
    return next(
        item.descriptor.action_id
        for item in catalog_lobby_actions(room, player_id)
        if item.action.kind is kind
    )


def join(room, player_id: str, display_name: str, now_ms: int):
    return join_lobby_room(
        room, PlayerId(player_id), display_name, now_ms=now_ms
    ).state


def apply(room, player_id: str, kind: LobbyActionKind, now_ms: int):
    return apply_lobby_action(
        room,
        PlayerId(player_id),
        action(room, player_id, kind),
        now_ms=now_ms,
    )


class LobbyNameAndSeatingTests(unittest.TestCase):
    def test_name_normalization_and_casefolded_uniqueness(self) -> None:
        self.assertEqual(
            normalize_display_name("  Ａli\u200bce   Smith  "), "Alice Smith"
        )
        self.assertEqual(normalize_display_name("Straße"), "Straße")

        room = create_lobby_room("room-1", "host", "Straße", now_ms=100)
        with self.assertRaises(LobbyDomainError) as caught:
            join_lobby_room(room, "member", "STRASSE", now_ms=101)
        self.assertEqual(caught.exception.code, "DISPLAY_NAME_TAKEN")

        for invalid in ("", " \u200b\x00 ", "x" * 65):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(LobbyDomainError) as invalid_name:
                    normalize_display_name(invalid)
                self.assertEqual(invalid_name.exception.code, "INVALID_DISPLAY_NAME")

    def test_host_uses_seat_zero_and_joins_use_lowest_empty_seat(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        self.assertEqual(room.seats[0].slot, 0)
        self.assertEqual(str(room.seats[0].controller.player_id), "host")  # type: ignore[union-attr]

        room = join(room, "member-1", "Member One", 101)
        room = join(room, "member-2", "Member Two", 102)
        occupied = {
            str(seat.controller.player_id): seat.slot  # type: ignore[union-attr]
            for seat in room.seats
            if seat.controller is not None
            and getattr(seat.controller, "type", None) == "external"
        }
        self.assertEqual(occupied, {"host": 0, "member-1": 1, "member-2": 2})

        removed = apply_lobby_action(
            room,
            "host",
            next(
                item.action
                for item in catalog_lobby_actions(room, "host")
                if item.action.kind is LobbyActionKind.REMOVE_PLAYER
                and str(item.action.target_player_id) == "member-1"
            ),
            now_ms=103,
        ).state
        rejoined = join(removed, "member-3", "Member Three", 104)
        seat = next(
            value
            for value in rejoined.seats
            if getattr(value.controller, "player_id", None) == PlayerId("member-3")
        )
        self.assertEqual(seat.slot, 1)


class LobbyCatalogAndPrivacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        self.room = join(self.room, "member", "Member", 101)

    def test_host_and_member_receive_different_opaque_catalogs(self) -> None:
        host_catalog = catalog_lobby_actions(self.room, "host")
        member_catalog = catalog_lobby_actions(self.room, "member")
        host_kinds = {item.action.kind for item in host_catalog}
        member_kinds = {item.action.kind for item in member_catalog}

        self.assertTrue(
            {
                LobbyActionKind.ADD_BOT,
                LobbyActionKind.FILL_BOTS,
                LobbyActionKind.REMOVE_PLAYER,
                LobbyActionKind.ROTATE_INVITE,
            }.issubset(host_kinds)
        )
        self.assertEqual(
            member_kinds, {LobbyActionKind.READY, LobbyActionKind.LEAVE}
        )
        invitation_actions = [
            item
            for item in host_catalog
            if item.descriptor.presentation_slot == "invitation"
        ]
        self.assertEqual(len(invitation_actions), 1)
        self.assertEqual(
            invitation_actions[0].action.kind, LobbyActionKind.ROTATE_INVITE
        )
        self.assertTrue(
            all(
                item.descriptor.presentation_slot == "roomActions"
                for item in member_catalog
            )
        )
        self.assertTrue(
            all(re.fullmatch(r"[0-9a-f]{64}", item.descriptor.action_id)
                for item in host_catalog + member_catalog)
        )

        view = build_public_room_view(
            self.room,
            PlayerId("host"),
            server_time_ms=102,
            actions=tuple(item.descriptor for item in host_catalog),
        )
        public_json = view.canonical_json()
        self.assertNotIn("targetPlayerId", public_json)
        self.assertNotIn("targetSeatId", public_json)
        self.assertNotIn('"kind"', public_json)
        self.assertNotIn("removePlayer", public_json)

    def test_action_ids_are_viewer_and_revision_bound_and_forgery_is_rejected(self) -> None:
        host_leave = action_id(self.room, "host", LobbyActionKind.LEAVE)
        member_leave = action_id(self.room, "member", LobbyActionKind.LEAVE)
        self.assertNotEqual(host_leave, member_leave)
        self.assertEqual(
            resolve_lobby_action(self.room, "host", host_leave).kind,
            LobbyActionKind.LEAVE,
        )

        advanced = apply(self.room, "member", LobbyActionKind.READY, 102).state
        self.assertNotEqual(
            host_leave, action_id(advanced, "host", LobbyActionKind.LEAVE)
        )
        for forged in ("0" * 64, host_leave):
            with self.subTest(forged=forged):
                with self.assertRaises(LobbyDomainError) as caught:
                    resolve_lobby_action(advanced, "host", forged)
                self.assertEqual(caught.exception.code, "ACTION_NOT_AVAILABLE")

    def test_disconnected_viewer_cannot_resolve_ready_or_start_actions(self) -> None:
        solo = create_lobby_room("room-solo", "solo", "Solo", now_ms=100)
        offline = catalog_lobby_actions(
            solo,
            "solo",
            viewer_connected=False,
        )
        by_kind = {item.action.kind: item for item in offline}
        self.assertFalse(by_kind[LobbyActionKind.READY].descriptor.enabled)
        self.assertEqual(
            by_kind[LobbyActionKind.READY].descriptor.disabled_reason,
            "Reconnect before getting ready.",
        )
        self.assertFalse(
            by_kind[LobbyActionKind.START_AGAINST_BOTS].descriptor.enabled
        )
        self.assertEqual(
            by_kind[
                LobbyActionKind.START_AGAINST_BOTS
            ].descriptor.disabled_reason,
            "Reconnect before starting.",
        )
        for kind in (
            LobbyActionKind.READY,
            LobbyActionKind.START_AGAINST_BOTS,
        ):
            with self.subTest(kind=kind):
                with self.assertRaises(LobbyDomainError) as caught:
                    resolve_lobby_action(
                        solo,
                        "solo",
                        by_kind[kind].descriptor.action_id,
                        viewer_connected=False,
                    )
                self.assertEqual(caught.exception.code, "ACTION_NOT_AVAILABLE")
        self.assertTrue(by_kind[LobbyActionKind.LEAVE].descriptor.enabled)

        full = create_lobby_room("room-full", "host", "Host", now_ms=200)
        for number in range(1, 4):
            full = join(full, f"member-{number}", f"Member {number}", 200 + number)
        for offset, player_id in enumerate(
            ("host", "member-1", "member-2", "member-3"),
            start=10,
        ):
            full = apply(
                full,
                player_id,
                LobbyActionKind.READY,
                200 + offset,
            ).state
        start = next(
            item
            for item in catalog_lobby_actions(
                full,
                "host",
                viewer_connected=False,
            )
            if item.action.kind is LobbyActionKind.START_MATCH
        )
        self.assertFalse(start.descriptor.enabled)
        self.assertEqual(
            start.descriptor.disabled_reason,
            "Reconnect before starting.",
        )

    def test_public_player_presence_is_explicit_and_versioned(self) -> None:
        view = build_public_room_view(
            self.room,
            PlayerId("host"),
            server_time_ms=102,
            disconnected_players={"member": 300_000},
            presence_version=7,
        )
        players = {str(player.player_id): player for player in view.players}
        self.assertEqual(view.presence_version, 7)
        self.assertEqual(players["host"].connection_status, "CONNECTED")
        self.assertIsNone(players["host"].disconnect_expires_at_ms)
        self.assertEqual(players["member"].connection_status, "DISCONNECTED")
        self.assertEqual(players["member"].disconnect_expires_at_ms, 300_000)
        self.assertIn('"presenceVersion":7', view.canonical_json())


class LobbyRosterAndReadinessTests(unittest.TestCase):
    def test_bots_have_collision_free_names_are_publicly_ready_and_block_join(self) -> None:
        room = create_lobby_room("room-1", "host", "Bot 1", now_ms=100)
        filled = apply(room, "host", LobbyActionKind.FILL_BOTS, 101).state
        bot_names = [
            seat.occupant_name
            for seat in filled.seats
            if isinstance(seat.controller, AutomatedSeatController)
        ]
        self.assertEqual(bot_names, ["Bot 2", "Bot 3", "Bot 4"])

        view = build_public_room_view(
            filled, PlayerId("host"), server_time_ms=102
        )
        bot_occupants = [
            seat.occupant
            for seat in view.seats
            if seat.occupant is not None
            and seat.occupant.controller_type == "automated"
        ]
        self.assertEqual([value.ready for value in bot_occupants], [True, True, True])

        with self.assertRaises(LobbyDomainError) as caught:
            join_lobby_room(filled, "member", "Human", now_ms=103)
        self.assertEqual(caught.exception.code, "ROOM_FULL")

    def test_roster_changes_clear_every_human_readiness(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        room = join(room, "member", "Member", 101)
        room = apply(room, "host", LobbyActionKind.READY, 102).state
        room = apply(room, "member", LobbyActionKind.READY, 103).state
        self.assertTrue(all(player.ready for player in room.players))

        with_bot = apply(room, "host", LobbyActionKind.ADD_BOT, 104).state
        self.assertTrue(all(not player.ready for player in with_bot.players))
        self.assertEqual(with_bot.status, RoomStatus.WAITING_FOR_PLAYERS)

        host_ready = apply(with_bot, "host", LobbyActionKind.READY, 105).state
        member_ready = apply(host_ready, "member", LobbyActionKind.READY, 106).state
        joined = join(member_ready, "member-2", "Member Two", 107)
        self.assertTrue(all(not player.ready for player in joined.players))

    def test_unready_remove_bot_remove_player_and_invite_rotation_transitions(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        room = join(room, "member", "Member", 101)
        room = apply(room, "host", LobbyActionKind.READY, 102).state
        unready = apply(room, "host", LobbyActionKind.UNREADY, 103)
        self.assertEqual(unready.event_type, "playerReadinessChanged")
        self.assertFalse(unready.state.players[0].ready)

        with_bot = apply(unready.state, "host", LobbyActionKind.ADD_BOT, 104)
        self.assertEqual(with_bot.event_type, "botAdded")
        remove_bot = next(
            item.action
            for item in catalog_lobby_actions(with_bot.state, "host")
            if item.action.kind is LobbyActionKind.REMOVE_BOT
        )
        without_bot = apply_lobby_action(
            with_bot.state, "host", remove_bot, now_ms=105
        )
        self.assertEqual(without_bot.event_type, "botRemoved")
        self.assertFalse(
            any(
                isinstance(seat.controller, AutomatedSeatController)
                for seat in without_bot.state.seats
            )
        )

        filled = apply(
            without_bot.state, "host", LobbyActionKind.FILL_BOTS, 106
        ).state
        filled = apply(filled, "host", LobbyActionKind.READY, 107).state
        filled = apply(filled, "member", LobbyActionKind.READY, 108).state
        self.assertEqual(filled.status, RoomStatus.READY)
        rotated = apply(filled, "host", LobbyActionKind.ROTATE_INVITE, 109)
        self.assertTrue(rotated.rotate_invite)
        self.assertEqual(rotated.event_type, "inviteRotated")
        self.assertEqual(rotated.state.status, RoomStatus.READY)
        self.assertTrue(all(player.ready for player in rotated.state.players))

        remove_member = next(
            item.action
            for item in catalog_lobby_actions(rotated.state, "host")
            if item.action.kind is LobbyActionKind.REMOVE_PLAYER
        )
        removed = apply_lobby_action(
            rotated.state, "host", remove_member, now_ms=110
        )
        self.assertEqual(removed.event_type, "playerRemoved")
        self.assertEqual([str(player.player_id) for player in removed.state.players], ["host"])
        self.assertFalse(removed.state.players[0].ready)

    def test_host_transfer_uses_join_time_then_player_id_and_last_human_finishes(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        room = join(room, "player-z", "Zulu", 101)
        room = join(room, "player-a", "Alpha", 101)
        left = apply(room, "host", LobbyActionKind.LEAVE, 102)
        self.assertTrue(left.session_ended)
        self.assertEqual(left.additional_events[0][0], "hostTransferred")
        next_host = next(
            player for player in left.state.players if player.role is PlayerRole.HOST
        )
        self.assertEqual(str(next_host.player_id), "player-a")

        solo = create_lobby_room("room-2", "only-human", "Solo", now_ms=200)
        finished = apply(solo, "only-human", LobbyActionKind.LEAVE, 201)
        self.assertTrue(finished.session_ended)
        self.assertEqual(finished.state.status, RoomStatus.FINISHED)
        self.assertEqual(finished.state.players, ())
        self.assertTrue(all(seat.controller is None for seat in finished.state.seats))

    def test_disconnect_resets_only_actor_and_combines_host_transfer_events(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        room = join(room, "player-z", "Zulu", 101)
        room = join(room, "player-a", "Alpha", 101)
        room = apply(room, "host", LobbyActionKind.READY, 102).state
        room = apply(room, "player-z", LobbyActionKind.READY, 103).state

        disconnected = apply_lobby_disconnect(
            room,
            "host",
            {"player-z", "player-a"},
            now_ms=104,
        )

        self.assertIsNotNone(disconnected)
        state = disconnected.state  # type: ignore[union-attr]
        self.assertEqual(state.revision, room.revision + 1)
        players = {str(player.player_id): player for player in state.players}
        self.assertFalse(players["host"].ready)
        self.assertTrue(players["player-z"].ready)
        self.assertEqual(players["host"].role, PlayerRole.MEMBER)
        self.assertEqual(players["player-a"].role, PlayerRole.HOST)
        self.assertEqual(disconnected.event_type, "playerReadinessChanged")  # type: ignore[union-attr]
        self.assertEqual(  # type: ignore[union-attr]
            disconnected.event_details,
            {"playerId": "host", "ready": False},
        )
        self.assertEqual(  # type: ignore[union-attr]
            disconnected.additional_events,
            (
                (
                    "hostTransferred",
                    {"fromPlayerId": "host", "toPlayerId": "player-a"},
                ),
            ),
        )

    def test_disconnected_host_waits_until_earliest_connected_human_arrives(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        room = join(room, "late-id", "Earlier Join", 101)
        room = join(room, "early-id", "Later Join", 102)

        self.assertIsNone(
            apply_lobby_disconnect(room, "host", set(), now_ms=103)
        )
        transferred = reconcile_lobby_host(
            room,
            {"late-id", "early-id"},
            now_ms=104,
        )
        self.assertIsNotNone(transferred)
        host = next(  # type: ignore[union-attr]
            player
            for player in transferred.state.players
            if player.role is PlayerRole.HOST
        )
        self.assertEqual(str(host.player_id), "late-id")
        self.assertEqual(transferred.event_type, "hostTransferred")  # type: ignore[union-attr]

        ready_room = apply(room, "host", LobbyActionKind.READY, 105).state
        normalized = reconcile_lobby_host(
            ready_room,
            {"late-id"},
            now_ms=106,
        )
        self.assertIsNotNone(normalized)
        old_host = next(  # type: ignore[union-attr]
            player
            for player in normalized.state.players
            if str(player.player_id) == "host"
        )
        self.assertFalse(old_host.ready)
        self.assertEqual(normalized.event_type, "playerReadinessChanged")  # type: ignore[union-attr]
        self.assertEqual(  # type: ignore[union-attr]
            normalized.additional_events[0][0], "hostTransferred"
        )

    def test_disconnect_is_noop_for_unready_member_and_for_frozen_match(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        room = join(room, "member", "Member", 101)
        self.assertIsNone(
            apply_lobby_disconnect(room, "member", {"host"}, now_ms=102)
        )

        started = apply(
            create_lobby_room("room-2", "solo", "Solo", now_ms=200),
            "solo",
            LobbyActionKind.START_AGAINST_BOTS,
            201,
        ).state
        with self.assertRaises(LobbyDomainError) as caught:
            apply_lobby_disconnect(started, "solo", set(), now_ms=202)
        self.assertEqual(caught.exception.code, "ROOM_CLOSED")


class LobbyStartTests(unittest.TestCase):
    def test_four_humans_become_ready_and_start_a_pending_match_shell(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        for number in range(1, 4):
            room = join(room, f"player-{number}", f"Player {number}", 100 + number)
        for offset, player_id in enumerate(
            ("host", "player-1", "player-2", "player-3"), start=10
        ):
            room = apply(room, player_id, LobbyActionKind.READY, 100 + offset).state
        self.assertEqual(room.status, RoomStatus.READY)

        started = apply(room, "host", LobbyActionKind.START_MATCH, 120)
        state = started.state
        self.assertEqual(state.revision, room.revision + 1)
        self.assertEqual(state.status, RoomStatus.IN_MATCH)
        self.assertIsNotNone(state.match)
        self.assertEqual(state.match.status, MatchStatus.PENDING_SETUP)  # type: ignore[union-attr]
        self.assertIsNone(state.match.dealer_seat_id)  # type: ignore[union-attr]
        self.assertIsNone(state.match.current_hand)  # type: ignore[union-attr]
        self.assertEqual([balance.points for balance in state.match.balances], [0] * 4)  # type: ignore[union-attr]
        self.assertEqual(catalog_lobby_actions(state, "host"), ())

        view = build_public_room_view(state, PlayerId("host"), server_time_ms=121)
        self.assertIsNotNone(view.game)
        self.assertEqual(view.game.status, MatchStatus.PENDING_SETUP)  # type: ignore[union-attr]
        self.assertIsNone(view.game.dealer_seat_id)  # type: ignore[union-attr]
        self.assertEqual(view.actions, ())

        with self.assertRaises(LobbyDomainError) as closed:
            join_lobby_room(state, "late", "Late Player", now_ms=122)
        self.assertEqual(closed.exception.code, "ROOM_CLOSED")
        with self.assertRaises(LobbyDomainError) as frozen:
            apply_lobby_action(
                state,
                "host",
                LobbyAction(kind=LobbyActionKind.LEAVE),
                now_ms=122,
            )
        self.assertEqual(frozen.exception.code, "ROOM_CLOSED")

    def test_start_against_bots_is_atomic_and_emits_same_revision_facts(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        transition = apply(
            room, "host", LobbyActionKind.START_AGAINST_BOTS, 101
        )
        state = transition.state
        self.assertEqual(state.revision, 1)
        self.assertEqual(state.status, RoomStatus.IN_MATCH)
        self.assertEqual(sum(isinstance(seat.controller, AutomatedSeatController)
                             for seat in state.seats), 3)
        self.assertTrue(state.players[0].ready)
        self.assertEqual(
            [transition.event_type]
            + [event_type for event_type, _ in transition.additional_events],
            ["botsFilled", "playerReadinessChanged", "matchStarted"],
        )
        self.assertEqual(state.match.status, MatchStatus.PENDING_SETUP)  # type: ignore[union-attr]

    def test_only_host_can_start_or_update_configuration(self) -> None:
        room = create_lobby_room("room-1", "host", "Host", now_ms=100)
        room = join(room, "member", "Member", 101)
        with self.assertRaises(LobbyDomainError) as config_error:
            update_lobby_config(
                room, "member", GameConfig(), now_ms=102
            )
        self.assertEqual(config_error.exception.code, "HOST_REQUIRED")
        with self.assertRaises(LobbyDomainError) as start_error:
            apply_lobby_action(
                room,
                "member",
                LobbyAction(kind=LobbyActionKind.START_MATCH),
                now_ms=102,
            )
        self.assertEqual(start_error.exception.code, "HOST_REQUIRED")


if __name__ == "__main__":
    unittest.main()
