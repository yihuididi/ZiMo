"""Stable persistence failures with application-level meaning."""

from __future__ import annotations


class PersistenceError(RuntimeError):
    """Base class for repository failures with stable application meaning."""


class RoomAlreadyExistsError(PersistenceError):
    """Raised when a Durable Object has already been initialized."""


class RoomNotFoundError(PersistenceError):
    """Raised when a commit is attempted before room initialization."""


class RevisionConflictError(PersistenceError):
    """Raised when an optimistic compare-and-swap revision is stale."""

    def __init__(self, expected_revision: int, actual_revision: int | None) -> None:
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            "room revision conflict: "
            f"expected {expected_revision}, actual {actual_revision}"
        )


class CorruptRoomStateError(PersistenceError):
    """Raised when canonical state and its indexed metadata disagree."""


class UnsupportedSchemaVersionError(PersistenceError):
    """Raised when storage was written by a newer or inconsistent schema."""


class ProcessedCommandConflictError(PersistenceError):
    """Raised when a command id is reused for a different request."""


class PlayerProjectionError(PersistenceError):
    """Raised when authentication projections disagree with canonical state."""


class SocketTicketUnavailableError(PersistenceError):
    """Raised when a socket ticket is unknown, expired, stale, or consumed."""


__all__ = [
    "CorruptRoomStateError",
    "PersistenceError",
    "PlayerProjectionError",
    "ProcessedCommandConflictError",
    "RevisionConflictError",
    "RoomAlreadyExistsError",
    "RoomNotFoundError",
    "SocketTicketUnavailableError",
    "UnsupportedSchemaVersionError",
]
