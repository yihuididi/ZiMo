import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { PageHeading } from "../components/PageHeading";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { createRoom } from "../lib/api";
import { errorMessage } from "../lib/errors";
import { makeInvitePath, parseInviteLink } from "../lib/invite";
import { listStoredRooms, saveRoomSession } from "../lib/session";

export function HomePage() {
  const navigate = useNavigate();
  const [storedRooms] = useState(() => listStoredRooms());
  const [displayName, setDisplayName] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const createControllerRef = useRef<AbortController | null>(null);

  useDocumentTitle("ZiMo Mahjong");

  useEffect(
    () => () => {
      createControllerRef.current?.abort();
    },
    [],
  );

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (creating || createControllerRef.current) return;
    const name = displayName.trim();
    if (!name) return;
    setCreating(true);
    setCreateError(null);
    const controller = new AbortController();
    createControllerRef.current = controller;
    try {
      const response = await createRoom(name, controller.signal);
      if (controller.signal.aborted) return;
      saveRoomSession({
        version: 1,
        roomId: response.roomId,
        playerId: response.playerId,
        playerToken: response.playerToken,
        inviteToken: response.inviteToken,
      });
      navigate(`/rooms/${encodeURIComponent(response.roomId)}`);
    } catch (reason) {
      if (controller.signal.aborted) return;
      setCreateError(errorMessage(reason));
      setCreating(false);
    } finally {
      if (createControllerRef.current === controller) {
        createControllerRef.current = null;
      }
    }
  }

  function handleInvite(event: FormEvent) {
    event.preventDefault();
    if (creating || createControllerRef.current) return;
    const invitation = parseInviteLink(inviteLink);
    if (!invitation) {
      setInviteError(
        "Paste a complete invitation link, including its invite fragment.",
      );
      return;
    }
    setInviteError(null);
    navigate(makeInvitePath(invitation.roomId, invitation.inviteToken));
  }

  return (
    <main className="home-shell">
      <div className="home-brand">
        <span className="brand-mark" aria-hidden="true">
          四
        </span>
        <p className="eyebrow">Singapore Mahjong · Preview</p>
        <PageHeading>Gather your table.</PageHeading>
        <p>
          Open a private four-seat room, invite friends, or fill the table with
          bots. No account needed.
        </p>
      </div>

      <div className="entry-card">
        {storedRooms.length > 0 && (
          <section className="recent-rooms" aria-labelledby="recent-heading">
            <p className="step-label">Saved on this device</p>
            <h2 id="recent-heading">Rejoin a room</h2>
            <ul>
              {storedRooms.map(({ roomId }) => (
                <li key={roomId}>
                  <Link
                    aria-label={`Rejoin room ${roomId}`}
                    className="recent-room-link"
                    to={`/rooms/${encodeURIComponent(roomId)}`}
                  >
                    <span>Rejoin room</span>
                    <span aria-hidden="true">
                      {roomId.length > 18
                        ? `${roomId.slice(0, 10)}…${roomId.slice(-6)}`
                        : roomId}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <p className="fine-print">
              Access remains on this browser until you leave the room, are
              removed, or clear this site’s data.
            </p>
          </section>
        )}

        {storedRooms.length > 0 && (
          <div className="divider" aria-hidden="true">
            <span>or start another</span>
          </div>
        )}

        <section aria-labelledby="create-heading">
          <p className="step-label">Start a new table</p>
          <h2 id="create-heading">Create a room</h2>
          <form aria-busy={creating} onSubmit={handleCreate}>
            <label htmlFor="create-name">Your display name</label>
            <input
              id="create-name"
              name="displayName"
              autoComplete="nickname"
              maxLength={64}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="e.g. Mei"
              disabled={creating}
              required
            />
            <button
              aria-busy={creating}
              className="primary-action"
              type="submit"
              disabled={creating}
            >
              {creating ? "Creating room…" : "Create private room"}
            </button>
          </form>
          {createError && (
            <p className="message error" role="alert">
              {createError}
            </p>
          )}

          <div className="divider" aria-hidden="true">
            <span>or</span>
          </div>

          <form onSubmit={handleInvite}>
            <label htmlFor="invite-link">Already invited?</label>
            <div className="inline-form">
              <input
                id="invite-link"
                value={inviteLink}
                onChange={(event) => setInviteLink(event.target.value)}
                placeholder="Paste invitation link"
                inputMode="url"
                disabled={creating}
                required
              />
              <button
                className="secondary-action"
                type="submit"
                disabled={creating}
              >
                Open
              </button>
            </div>
          </form>
          {inviteError && (
            <p className="message error" role="alert">
              {inviteError}
            </p>
          )}
        </section>
      </div>
    </main>
  );
}
