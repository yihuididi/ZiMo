"""Durable socket-presence reconciliation for room orchestration."""

from __future__ import annotations

from collections.abc import Sequence

if __package__.startswith("app."):
    from ..game import PlayerId, RoomStatus
    from ..lobby import (
        LobbyDomainError,
        apply_lobby_disconnect,
        expire_disconnected_lobby_player,
        reconcile_lobby_host,
    )
    from ..persistence import PlayerPresenceRecord
else:  # pragma: no cover - Python Workers load modules from the app directory.
    from game import PlayerId, RoomStatus
    from lobby import (
        LobbyDomainError,
        apply_lobby_disconnect,
        expire_disconnected_lobby_player,
        reconcile_lobby_host,
    )
    from persistence import PlayerPresenceRecord

from .codec import require_non_negative_int, require_text
from .contracts import DISCONNECT_GRACE_MS


class RoomPresence:
    """Presence-side use cases layered on a :class:`RoomKernel`."""

    def player_connected(self, player_id: str, auth_generation: int) -> bool:
        """Reconcile one authenticated socket connection."""

        requested = (require_text(player_id, "player_id"), auth_generation)
        require_non_negative_int(auth_generation, "auth_generation")
        disconnected = {
            (presence.player_id, presence.auth_generation)
            for presence in self._repository.list_player_presence()
        }
        connected = {
            (record.player_id, record.auth_generation)
            for record in self._repository.list_player_records(
                include_revoked=False
            )
            if (record.player_id, record.auth_generation) not in disconnected
        }
        connected.add(requested)
        return self.reconcile_socket_presence(tuple(sorted(connected)))

    def reconcile_socket_presence(
        self,
        connected_identities: Sequence[tuple[str, int]],
    ) -> bool:
        """Atomically reconcile a batch of live sockets and any host handoff."""

        connected = self._active_socket_identities(connected_identities)
        if not connected:
            return False
        state = self._require_room()
        connected_player_ids = {
            PlayerId(player_id) for player_id, _generation in connected
        }
        transition = None
        if state.status not in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
            transition = reconcile_lobby_host(
                state,
                connected_player_ids,
                now_ms=self._now_ms(),
            )
        if transition is None:
            return self._repository.set_players_connected(connected)
        self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(transition.state),
            events=self._transition_events(transition),
            clear_player_presence=connected,
        )
        return True

    def player_disconnected(
        self,
        player_id: str,
        auth_generation: int,
        connected_identities: Sequence[tuple[str, int]] | None = None,
    ) -> bool:
        """Persist a final-socket close and its canonical lobby consequences."""

        require_text(player_id, "player_id")
        require_non_negative_int(auth_generation, "auth_generation")
        player = self._repository.get_player(player_id)
        if player is None or player.auth_generation != auth_generation:
            return False
        if any(
            presence.player_id == player_id
            and presence.auth_generation == auth_generation
            for presence in self._repository.list_player_presence()
        ):
            return False
        state = self._require_room()
        now_ms = self._now_ms()
        expires_at_ms = (
            None
            if state.status in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}
            else now_ms + DISCONNECT_GRACE_MS
        )
        presence = PlayerPresenceRecord(
            player_id=player_id,
            auth_generation=auth_generation,
            disconnected_at_ms=now_ms,
            disconnect_expires_at_ms=expires_at_ms,
        )
        transition = None
        if state.status not in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
            if connected_identities is None:
                disconnected_ids = {
                    item.player_id
                    for item in self._repository.list_player_presence()
                }
                disconnected_ids.add(player_id)
                connected_player_ids = {
                    player.player_id
                    for player in state.players
                    if str(player.player_id) not in disconnected_ids
                }
            else:
                connected_player_ids = {
                    PlayerId(identity[0])
                    for identity in self._active_socket_identities(
                        connected_identities
                    )
                    if identity != (player_id, auth_generation)
                }
            transition = apply_lobby_disconnect(
                state,
                player_id,
                connected_player_ids,
                now_ms=now_ms,
            )
        if transition is None:
            return self._repository.set_player_disconnected(presence)
        self._commit(
            transition.state,
            expected_revision=state.revision,
            players=self._player_records_for_state(transition.state),
            events=self._transition_events(transition),
            upsert_player_presence=presence,
        )
        return True

    def next_presence_alarm_ms(self) -> int | None:
        """Return the earliest pending pre-match disconnect deadline."""

        return self._repository.next_presence_alarm_ms()

    def expire_disconnected_players(
        self,
        connected_identities: Sequence[tuple[str, int]],
    ) -> tuple[str, ...]:
        """Idempotently evict due pre-match players that remain offline."""

        connected = set(self._active_socket_identities(connected_identities))
        self.reconcile_socket_presence(tuple(sorted(connected)))

        state = self._require_room()
        if state.status in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
            self._repository.clear_presence_expiration_deadlines()
            return ()

        now_ms = self._now_ms()
        due = tuple(
            presence
            for presence in self._repository.list_player_presence()
            if presence.disconnect_expires_at_ms is not None
            and presence.disconnect_expires_at_ms <= now_ms
            and (presence.player_id, presence.auth_generation) not in connected
        )
        due = tuple(
            sorted(
                due,
                key=lambda presence: (
                    presence.disconnect_expires_at_ms or 0,
                    presence.player_id,
                ),
            )
        )
        expired: list[str] = []
        for presence in due:
            current = self._require_room()
            if current.status in {RoomStatus.IN_MATCH, RoomStatus.FINISHED}:
                self._repository.clear_presence_expiration_deadlines()
                break
            active_presence = {
                (item.player_id, item.auth_generation): item
                for item in self._repository.list_player_presence()
            }.get((presence.player_id, presence.auth_generation))
            if (
                active_presence is None
                or active_presence.disconnect_expires_at_ms is None
                or active_presence.disconnect_expires_at_ms > now_ms
            ):
                continue
            try:
                transition = expire_disconnected_lobby_player(
                    current,
                    presence.player_id,
                    now_ms=now_ms,
                )
            except LobbyDomainError:
                # An at-least-once alarm may observe an already-applied removal.
                continue
            self._commit(
                transition.state,
                expected_revision=current.revision,
                players=self._player_records_for_state(transition.state),
                events=self._transition_events(transition),
            )
            expired.append(presence.player_id)
        return tuple(expired)


__all__ = ["RoomPresence"]
