"""Platform-neutral orchestration for one authoritative Mahjong room."""

from __future__ import annotations

from collections.abc import Sequence

if __package__:
    from .game import RoomState
    from .persistence import (
        PlayerRecord,
        ProcessedCommandRecord,
        ProjectedAuditEvent,
        RoomRepository,
        SocketTicketRecord,
    )
else:  # Python Workers load ``app/main.py`` modules from the app directory.
    from game import RoomState
    from persistence import (
        PlayerRecord,
        ProcessedCommandRecord,
        ProjectedAuditEvent,
        RoomRepository,
        SocketTicketRecord,
    )


class RoomOrchestrator:
    """Coordinates validation, persistence, and a disposable state cache.

    The repository always commits before ``_cached_state`` changes.  Milestone
    1 has no broadcasting; a later adapter can safely broadcast only after
    these methods return.
    """

    def __init__(self, repository: RoomRepository) -> None:
        self._repository = repository
        self._cached_state: RoomState | None = None

    @property
    def cached_state(self) -> RoomState | None:
        return self._cached_state

    def initialize_room(
        self,
        snapshot_json: str,
        *,
        players: Sequence[PlayerRecord] = (),
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        socket_tickets: Sequence[SocketTicketRecord] = (),
    ) -> RoomState:
        """Validate and durably initialize a canonical room snapshot."""

        if not isinstance(snapshot_json, str):
            raise TypeError("snapshot_json must be a string")
        state = RoomState.model_validate_json(snapshot_json)
        persisted = self._repository.create_room(
            state,
            players=players,
            events=events,
            processed_commands=processed_commands,
            socket_tickets=socket_tickets,
        )
        self._cached_state = persisted
        return persisted

    def load_room(self) -> RoomState | None:
        """Discard any cache and reconstruct solely from canonical SQL state."""

        persisted = self._repository.load_room()
        self._cached_state = persisted
        return persisted

    def commit_room(
        self,
        state: RoomState,
        *,
        expected_revision: int,
        players: Sequence[PlayerRecord] | None = None,
        events: Sequence[ProjectedAuditEvent] = (),
        processed_commands: Sequence[ProcessedCommandRecord] = (),
        socket_tickets: Sequence[SocketTicketRecord] = (),
    ) -> RoomState:
        """Persist a complete revision before making it visible in memory."""

        persisted = self._repository.commit(
            state,
            expected_revision=expected_revision,
            players=players,
            events=events,
            processed_commands=processed_commands,
            socket_tickets=socket_tickets,
        )
        self._cached_state = persisted
        return persisted


__all__ = ["RoomOrchestrator"]
