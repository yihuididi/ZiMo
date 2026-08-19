import { useEffect, useState } from "react";

import {
  removeStoredInviteToken,
  type RoomSession,
} from "../../lib/session";
import type { PlayerRole } from "../../lib/types";

interface UseInviteCapabilityOptions {
  session: RoomSession;
  viewerRole: PlayerRole | undefined;
  onSessionChange: (session: RoomSession) => void;
}

export function useInviteCapability({
  session,
  viewerRole,
  onSessionChange,
}: UseInviteCapabilityOptions): string | null {
  const [warning, setWarning] = useState<string | null>(null);

  useEffect(() => {
    if (viewerRole === undefined || viewerRole === "HOST" || !session.inviteToken) {
      return;
    }
    const removal = removeStoredInviteToken(session);
    onSessionChange(removal.session);
    if (removal.storageStatus === "cleared") {
      setWarning(
        "Saved access on this device was cleared because browser storage could not safely remove the former host invitation. Keep this page open to remain in the room.",
      );
    } else if (removal.storageStatus === "failed") {
      setWarning(
        "This browser could not remove the former host invitation from saved storage. Clear this site's stored data before using a shared device.",
      );
    }
  }, [onSessionChange, session, viewerRole]);

  return warning;
}
