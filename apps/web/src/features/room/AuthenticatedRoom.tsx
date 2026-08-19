import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useRoomSocket } from "../../hooks/useRoomSocket";
import {
  clearRoomSession,
  type RoomSession,
} from "../../lib/session";
import type { PublicRoomView } from "../../lib/types";
import { LobbyView } from "./lobby/LobbyView";
import { useAuthoritativeRoomView } from "./useAuthoritativeRoomView";
import { useInviteCapability } from "./useInviteCapability";
import { useRoomCommands } from "./useRoomCommands";

interface AuthenticatedRoomProps {
  roomId: string;
  session: RoomSession;
  initialView: PublicRoomView | null;
  onSessionChange: (session: RoomSession) => void;
  onSessionLost: () => void;
  onSessionValidated: () => void;
}

function LoadingRoom({ error }: { error: string | null }) {
  useDocumentTitle("Opening room · ZiMo Mahjong");
  return (
    <main className="page-shell loading-shell" aria-live="polite">
      <div className="loading-mark" aria-hidden="true">
        四
      </div>
      <p>Opening your room…</p>
      {error && <p className="message error">{error}</p>}
    </main>
  );
}

export function AuthenticatedRoom({
  roomId,
  session,
  initialView,
  onSessionChange,
  onSessionLost,
  onSessionValidated,
}: AuthenticatedRoomProps) {
  const navigate = useNavigate();
  const { view, acceptView, getCurrentView } = useAuthoritativeRoomView(
    initialView,
    onSessionValidated,
  );

  const revokeSession = useCallback(() => {
    clearRoomSession(roomId);
    onSessionLost();
  }, [onSessionLost, roomId]);

  const endSession = useCallback(() => {
    clearRoomSession(roomId);
    navigate("/");
  }, [navigate, roomId]);

  const connection = useRoomSocket({
    roomId,
    playerToken: session.playerToken,
    onView: acceptView,
    onSessionEnded: revokeSession,
  });

  const viewerRole = view?.players.find(
    (player) => player.playerId === view.viewerPlayerId,
  )?.role;
  const roomWarning = useInviteCapability({
    session,
    viewerRole,
    onSessionChange,
  });
  const commands = useRoomCommands({
    roomId,
    session,
    acceptView,
    getCurrentView,
    onSessionChange,
    onSessionEnded: endSession,
    onSessionRevoked: revokeSession,
  });

  if (!view) return <LoadingRoom error={connection.error} />;

  return (
    <LobbyView
      roomId={roomId}
      session={session}
      view={view}
      connection={connection}
      roomWarning={roomWarning}
      operationsByActionId={commands.operationsByActionId}
      recoverableOperations={commands.recoverableOperations}
      feedback={commands.feedback}
      onRunAction={commands.runAction}
      onRetryAction={commands.retryAction}
    />
  );
}
