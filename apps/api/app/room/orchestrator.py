"""Public room-service composition over one shared persistence kernel."""

from __future__ import annotations

from .commands import RoomCommands
from .gameplay import RoomGameplay
from .kernel import RoomKernel
from .presence import RoomPresence


class RoomOrchestrator(RoomCommands, RoomGameplay, RoomPresence, RoomKernel):
    """Compose command and presence use cases around one repository/cache owner."""


__all__ = ["RoomOrchestrator"]
