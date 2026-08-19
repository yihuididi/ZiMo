import { useLayoutEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { AuthenticatedRoom } from "../features/room/AuthenticatedRoom";
import { JoinRoom } from "../features/room/JoinRoom";
import { LostSession } from "../features/room/LostSession";
import { readInviteToken, scrubInviteFragment } from "../lib/invite";
import {
  loadRoomSession,
  touchRoomSession,
} from "../lib/session";
import type { PublicRoomView } from "../lib/types";
import { NotFoundPage } from "./NotFoundPage";

function RoomPage({ roomId }: { roomId: string }) {
  const [capturedInviteToken, setCapturedInviteToken] = useState(() =>
    readInviteToken(window.location.hash),
  );
  const [session, setSession] = useState(() => {
    const stored = loadRoomSession(roomId);
    if (stored) touchRoomSession(stored);
    return stored;
  });
  const [initialView, setInitialView] = useState<PublicRoomView | null>(null);

  useLayoutEffect(() => {
    // Remove the reusable invite capability before the room UI is painted.
    scrubInviteFragment();
  }, []);

  if (!session) {
    if (capturedInviteToken) {
      return (
        <JoinRoom
          roomId={roomId}
          inviteToken={capturedInviteToken}
          onJoined={(joinedSession, view) => {
            setCapturedInviteToken(null);
            setInitialView(view);
            setSession(joinedSession);
          }}
        />
      );
    }
    return <LostSession roomId={roomId} />;
  }

  return (
    <AuthenticatedRoom
      roomId={roomId}
      session={session}
      initialView={initialView}
      onSessionChange={setSession}
      onSessionValidated={() => setCapturedInviteToken(null)}
      onSessionLost={() => setSession(null)}
    />
  );
}

export function RoomRoute() {
  const { roomId } = useParams();
  return roomId ? (
    <RoomPage key={roomId} roomId={roomId} />
  ) : (
    <NotFoundPage />
  );
}
