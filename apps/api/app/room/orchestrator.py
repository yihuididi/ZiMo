"""Public room-service composition over one shared persistence kernel."""

from __future__ import annotations

from .commands import RoomCommands
from .kernel import RoomKernel
from .presence import RoomPresence


class RoomOrchestrator(RoomCommands, RoomPresence, RoomKernel):
    """Compose command and presence use cases around one repository/cache owner."""


__all__ = ["RoomOrchestrator"]
