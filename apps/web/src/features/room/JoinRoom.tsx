import { type FormEvent, useState } from "react";

import { BrandLink } from "../../components/BrandLink";
import { PageHeading } from "../../components/PageHeading";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { joinRoom } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { saveRoomSession, type RoomSession } from "../../lib/session";
import type { PublicRoomView } from "../../lib/types";

interface JoinRoomProps {
  roomId: string;
  inviteToken: string;
  onJoined: (session: RoomSession, view: PublicRoomView) => void;
}

export function JoinRoom({ roomId, inviteToken, onJoined }: JoinRoomProps) {
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useDocumentTitle("Join the table · ZiMo Mahjong");

  async function handleJoin(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const name = displayName.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      const response = await joinRoom(roomId, inviteToken, name);
      const session: RoomSession = {
        version: 1,
        roomId,
        playerId: response.playerId,
        playerToken: response.playerToken,
      };
      saveRoomSession(session);
      onJoined(session, response.view);
    } catch (reason) {
      setError(errorMessage(reason));
      setBusy(false);
    }
  }

  return (
    <main className="page-shell narrow-shell">
      <BrandLink />
      <section className="entry-card join-card" aria-labelledby="join-heading">
        <p className="step-label">Private invitation</p>
        <PageHeading id="join-heading">Join the table</PageHeading>
        <p>Choose the name the other players will see in this room.</p>
        <form aria-busy={busy} onSubmit={handleJoin}>
          <label htmlFor="join-name">Your display name</label>
          <input
            id="join-name"
            autoFocus
            autoComplete="nickname"
            maxLength={64}
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="e.g. Wei"
            disabled={busy}
            required
          />
          <button
            aria-busy={busy}
            className="primary-action"
            type="submit"
            disabled={busy}
          >
            {busy ? "Joining…" : "Take a seat"}
          </button>
        </form>
        {error && (
          <p className="message error" role="alert">
            {error}
          </p>
        )}
      </section>
    </main>
  );
}
