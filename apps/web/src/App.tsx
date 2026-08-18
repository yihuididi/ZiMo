import {
  type FormEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";

import { useRoomSocket } from "./hooks/useRoomSocket";
import {
  ApiError,
  createRoom,
  getRoom,
  joinRoom,
  submitCommand,
} from "./lib/api";
import {
  makeInvitePath,
  makeInviteUrl,
  parseInviteLink,
  readInviteToken,
  scrubInviteFragment,
} from "./lib/invite";
import {
  clearRoomSession,
  listStoredRooms,
  loadRoomSession,
  removeStoredInviteToken,
  RoomSessionStorageError,
  saveRoomSession,
  touchRoomSession,
  updateStoredInviteToken,
  type RoomSession,
} from "./lib/session";
import type {
  OpaqueActionDescriptor,
  PublicRoomView,
  PublicSeatView,
} from "./lib/types";

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong.";
}

function BrandLink() {
  return (
    <Link className="brand-link" to="/">
      <span aria-hidden="true">四</span>
      <span>ZiMo Mahjong</span>
    </Link>
  );
}

function HomePage() {
  const navigate = useNavigate();
  const [storedRooms] = useState(() => listStoredRooms());
  const [displayName, setDisplayName] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    const name = displayName.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      const response = await createRoom(name);
      saveRoomSession({
        version: 1,
        roomId: response.roomId,
        playerId: response.playerId,
        playerToken: response.playerToken,
        inviteToken: response.inviteToken,
      });
      navigate(`/rooms/${encodeURIComponent(response.roomId)}`);
    } catch (reason) {
      setError(errorMessage(reason));
      setBusy(false);
    }
  }

  function handleInvite(event: FormEvent) {
    event.preventDefault();
    const invitation = parseInviteLink(inviteLink);
    if (!invitation) {
      setError("Paste a complete invitation link, including its invite fragment.");
      return;
    }
    setError(null);
    navigate(makeInvitePath(invitation.roomId, invitation.inviteToken));
  }

  return (
    <main className="home-shell">
      <div className="home-brand">
        <span className="brand-mark" aria-hidden="true">
          四
        </span>
        <p className="eyebrow">Singapore Mahjong · Preview</p>
        <h1>Gather your table.</h1>
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
          <form onSubmit={handleCreate}>
            <label htmlFor="create-name">Your display name</label>
            <input
              id="create-name"
              name="displayName"
              autoComplete="nickname"
              maxLength={64}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="e.g. Mei"
              required
            />
            <button className="primary-action" type="submit" disabled={busy}>
              {busy ? "Creating room…" : "Create private room"}
            </button>
          </form>

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
                required
              />
              <button className="secondary-action" type="submit">
                Open
              </button>
            </div>
          </form>
          {error && (
            <p className="message error" role="alert">
              {error}
            </p>
          )}
        </section>
      </div>
    </main>
  );
}

function JoinRoom({
  roomId,
  inviteToken,
  onJoined,
}: {
  roomId: string;
  inviteToken: string;
  onJoined: (session: RoomSession, view: PublicRoomView) => void;
}) {
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleJoin(event: FormEvent) {
    event.preventDefault();
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
        <h1 id="join-heading">Join the table</h1>
        <p>Choose the name the other players will see in this room.</p>
        <form onSubmit={handleJoin}>
          <label htmlFor="join-name">Your display name</label>
          <input
            id="join-name"
            autoFocus
            autoComplete="nickname"
            maxLength={64}
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="e.g. Wei"
            required
          />
          <button className="primary-action" type="submit" disabled={busy}>
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

function LostSession({ roomId }: { roomId: string }) {
  return (
    <main className="page-shell narrow-shell">
      <BrandLink />
      <section className="entry-card lost-card" aria-labelledby="lost-heading">
        <span className="lost-icon" aria-hidden="true">
          ↻
        </span>
        <h1 id="lost-heading">This room session is unavailable</h1>
        <p>
          No valid player access is stored on this device. It may have been
          removed, revoked, or cleared from this browser.
        </p>
        <p className="room-reference">Room {roomId}</p>
        <Link className="primary-action link-action" to="/">
          Return home
        </Link>
      </section>
    </main>
  );
}

function seatDescription(seat: PublicSeatView, viewerPlayerId: string) {
  const occupant = seat.occupant;
  if (!occupant) {
    return { name: "Open seat", kind: "Waiting", ready: null };
  }
  const name = occupant.displayName ?? "Mahjong Bot";
  const tags: string[] = [];
  if (occupant.playerId === viewerPlayerId) tags.push("You");
  if (occupant.role === "HOST") tags.push("Host");
  return {
    name,
    kind:
      occupant.controllerType === "automated"
        ? "Bot"
        : tags.length > 0
          ? tags.join(" · ")
          : "Player",
    ready: occupant.ready,
  };
}

function remainingDisconnectSeconds(
  disconnectExpiresAtMs: number,
  estimatedServerTimeMs: number,
) {
  return Math.max(
    0,
    Math.ceil((disconnectExpiresAtMs - estimatedServerTimeMs) / 1_000),
  );
}

function formatCountdown(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function DisconnectedStatus({
  disconnectExpiresAtMs,
  serverTimeMs,
}: {
  disconnectExpiresAtMs: number | null;
  serverTimeMs: number;
}) {
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(() =>
    disconnectExpiresAtMs === null
      ? null
      : remainingDisconnectSeconds(disconnectExpiresAtMs, serverTimeMs),
  );

  useEffect(() => {
    if (disconnectExpiresAtMs === null) {
      setRemainingSeconds(null);
      return;
    }

    const clientBaselineMs = performance.now();
    let timerId: number | undefined;
    const stopTimer = () => {
      if (timerId === undefined) return;
      window.clearInterval(timerId);
      timerId = undefined;
    };
    const update = () => {
      // The server clock is authoritative. The browser contributes only the
      // monotonic time elapsed since this view was received.
      const estimatedServerTimeMs =
        serverTimeMs + Math.max(0, performance.now() - clientBaselineMs);
      const next = remainingDisconnectSeconds(
        disconnectExpiresAtMs,
        estimatedServerTimeMs,
      );
      setRemainingSeconds(next);
      if (next === 0) stopTimer();
    };

    const initial = remainingDisconnectSeconds(
      disconnectExpiresAtMs,
      serverTimeMs,
    );
    setRemainingSeconds(initial);
    if (initial > 0) {
      timerId = window.setInterval(update, 1_000);
    }
    return stopTimer;
  }, [disconnectExpiresAtMs, serverTimeMs]);

  return (
    <div className="disconnected-status" role="status" aria-live="polite">
      <span className="disconnected-chip">Disconnected</span>
      {remainingSeconds !== null && (
        <span className="disconnect-countdown">
          {remainingSeconds === 0
            ? "Removing…"
            : `Removing in ${formatCountdown(remainingSeconds)}`}
        </span>
      )}
    </div>
  );
}

function SeatList({ view }: { view: PublicRoomView }) {
  const seats = useMemo(
    () => [...view.seats].sort((left, right) => left.slot - right.slot),
    [view.seats],
  );
  const playersById = useMemo(
    () => new Map(view.players.map((player) => [player.playerId, player])),
    [view.players],
  );
  return (
    <ol className="seat-grid" aria-label="Table seats">
      {seats.map((seat) => {
        const occupant = seatDescription(seat, view.viewerPlayerId);
        const player = seat.occupant?.playerId
          ? playersById.get(seat.occupant.playerId)
          : undefined;
        return (
          <li className={seat.occupant ? "seat occupied" : "seat empty"} key={seat.seatId}>
            <div className="seat-number" aria-hidden="true">
              {seat.slot + 1}
            </div>
            <div className="seat-copy">
              <strong>{occupant.name}</strong>
              <span>{seat.wind ? `${seat.wind} · ` : ""}{occupant.kind}</span>
            </div>
            {(occupant.ready !== null || player?.connectionStatus === "DISCONNECTED") && (
              <div className="seat-statuses">
                {occupant.ready !== null && (
                  <span className={occupant.ready ? "ready-chip" : "waiting-chip"}>
                    {occupant.ready ? "Ready" : "Not ready"}
                  </span>
                )}
                {player?.connectionStatus === "DISCONNECTED" && (
                  <DisconnectedStatus
                    disconnectExpiresAtMs={player.disconnectExpiresAtMs}
                    serverTimeMs={view.serverTimeMs}
                  />
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function RulesCard({ view }: { view: PublicRoomView }) {
  const flag = (enabled: boolean) => (enabled ? "Enabled" : "Disabled");
  return (
    <section className="panel rules-panel" aria-labelledby="rules-heading">
      <div className="panel-heading">
        <div>
          <p className="step-label">Preview ruleset</p>
          <h2 id="rules-heading">Singapore Mahjong</h2>
        </div>
        <span className="read-only-chip">Read only</span>
      </div>
      <dl className="rules-list">
        <div>
          <dt>Ruleset</dt>
          <dd>{view.rulesetId} · v{view.rulesetVersion}</dd>
        </div>
        <div>
          <dt>Fan range</dt>
          <dd>{view.config.minimumFan}–{view.config.maximumFan} fan</dd>
        </div>
        <div>
          <dt>Shooter mode</dt>
          <dd>{view.config.shooterMode ? "On" : "Off"}</dd>
        </div>
        <div>
          <dt>Payouts</dt>
          <dd>{view.config.payoutTable.join(" · ")}</dd>
        </div>
      </dl>
      <div className="rule-details">
        <details>
          <summary>Payments and bonuses</summary>
          <dl>
            <div><dt>Kong (one payer)</dt><dd>{view.config.kongOnePayment}</dd></div>
            <div><dt>Kong (three payers)</dt><dd>{view.config.kongThreePayment}</dd></div>
            <div><dt>Complete animals</dt><dd>{view.config.completeAnimalSetPayment}</dd></div>
            <div><dt>Complete flowers</dt><dd>{view.config.completeFlowerSetPayment}</dd></div>
            <div><dt>Complete seasons</dt><dd>{view.config.completeSeasonSetPayment}</dd></div>
            <div><dt>Animal pair</dt><dd>{view.config.animalPairPayment}</dd></div>
            <div><dt>Flower/season pair</dt><dd>{view.config.flowerSeasonPairPayment}</dd></div>
            <div><dt>Initial thirteen pair</dt><dd>{view.config.initialThirteenPairPayment}</dd></div>
          </dl>
        </details>
        <details>
          <summary>Thresholds and variations</summary>
          <dl>
            <div><dt>Fresh discard threshold</dt><dd>{view.config.freshDiscardThreshold}</dd></div>
            <div><dt>Fresh Kong threshold</dt><dd>{view.config.freshKongThreshold}</dd></div>
            <div><dt>Seven pairs</dt><dd>{flag(view.config.sevenPairsEnabled)}</dd></div>
            <div><dt>Fresh Kong pays all</dt><dd>{flag(view.config.freshKongPayAllEnabled)}</dd></div>
            <div><dt>Rob a four-tile Kong</dt><dd>{flag(view.config.kongFourRobberyEnabled)}</dd></div>
            <div><dt>Concealed self-draw bonus</dt><dd>{flag(view.config.concealedSelfDrawBonusEnabled)}</dd></div>
            <div><dt>Automatic dragon wins</dt><dd>{flag(view.config.automaticDragonWinsEnabled)}</dd></div>
            <div><dt>Automatic wind wins</dt><dd>{flag(view.config.automaticWindWinsEnabled)}</dd></div>
            <div><dt>Extra self-draw points</dt><dd>{view.config.extraSelfDrawPoints}</dd></div>
          </dl>
        </details>
      </div>
      <p className="fine-print">
        Settings are fixed for this preview milestone and freeze when the match
        starts.
      </p>
    </section>
  );
}

interface PendingCommand {
  commandId: string;
  actionId: string;
  expectedRevision: number;
}

function Lobby({
  roomId,
  session,
  initialView,
  onSessionChange,
  onSessionLost,
  onSessionValidated,
}: {
  roomId: string;
  session: RoomSession;
  initialView: PublicRoomView | null;
  onSessionChange: (session: RoomSession) => void;
  onSessionLost: () => void;
  onSessionValidated: () => void;
}) {
  const navigate = useNavigate();
  const [view, setView] = useState(initialView);
  const [pendingByAction, setPendingByAction] = useState<
    Record<string, PendingCommand>
  >({});
  const [retryCommand, setRetryCommand] = useState<PendingCommand | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const latestViewRef = useRef(initialView);

  const acceptView = useCallback((incoming: PublicRoomView) => {
    onSessionValidated();
    const current = latestViewRef.current;
    if (current) {
      if (incoming.revision < current.revision) return false;
      if (
        incoming.revision === current.revision &&
        incoming.presenceVersion < current.presenceVersion
      ) {
        return false;
      }
      if (
        incoming.revision === current.revision &&
        incoming.presenceVersion === current.presenceVersion &&
        incoming.serverTimeMs < current.serverTimeMs
      ) {
        return false;
      }
    }
    latestViewRef.current = incoming;
    setView(incoming);
    return true;
  }, [onSessionValidated]);

  const viewerRole = view?.players.find(
    (player) => player.playerId === view.viewerPlayerId,
  )?.role;

  useEffect(() => {
    if (!view || viewerRole === "HOST" || !session.inviteToken) return;
    const removal = removeStoredInviteToken(session);
    onSessionChange(removal.session);
    setCopied(false);
    if (removal.storageStatus === "cleared") {
      setActionError(
        "Saved access on this device was cleared because browser storage could not safely remove the former host invitation. Keep this page open to remain in the room.",
      );
    } else if (removal.storageStatus === "failed") {
      setActionError(
        "This browser could not remove the former host invitation from saved storage. Clear this site's stored data before using a shared device.",
      );
    }
  }, [onSessionChange, session, view, viewerRole]);

  const loseSession = useCallback(() => {
    clearRoomSession(roomId);
    onSessionLost();
  }, [onSessionLost, roomId]);

  const connection = useRoomSocket({
    roomId,
    playerToken: session.playerToken,
    onView: acceptView,
    onSessionEnded: loseSession,
  });

  function removePending(command: PendingCommand) {
    setPendingByAction((current) => {
      if (current[command.actionId]?.commandId !== command.commandId) {
        return current;
      }
      const updated = { ...current };
      delete updated[command.actionId];
      return updated;
    });
  }

  async function executeCommand(command: PendingCommand) {
    setPendingByAction((current) => ({
      ...current,
      [command.actionId]: command,
    }));
    setRetryCommand((current) =>
      current?.commandId === command.commandId ? null : current,
    );
    setActionError(null);
    setNotice(null);
    try {
      const response = await submitCommand(roomId, session.playerToken, command);
      if (response.type === "sessionEnded") {
        clearRoomSession(roomId);
        navigate("/");
        return;
      }
      acceptView(response.view);
      const currentView = latestViewRef.current;
      const currentViewer = currentView?.players.find(
        (player) => player.playerId === currentView.viewerPlayerId,
      );
      if (
        response.inviteToken &&
        currentView?.revision === response.view.revision &&
        currentViewer?.role === "HOST"
      ) {
        try {
          const updated = updateStoredInviteToken(session, response.inviteToken);
          onSessionChange(updated);
          setCopied(false);
        } catch (reason) {
          if (reason instanceof RoomSessionStorageError) {
            removePending(command);
            setRetryCommand(command);
            setActionError(
              "The invitation was rotated, but this browser could not store it. Enable persistent browser storage, then retry safely to recover the same invitation.",
            );
            return;
          }
          throw reason;
        }
      }
      removePending(command);
      setRetryCommand((current) =>
        current?.commandId === command.commandId ? null : current,
      );
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        try {
          acceptView(await getRoom(roomId, session.playerToken));
          setNotice("The room changed first. Your view has been refreshed.");
        } catch (refreshReason) {
          if (
            refreshReason instanceof ApiError &&
            refreshReason.status === 401
          ) {
            loseSession();
            return;
          }
          setActionError(errorMessage(refreshReason));
        }
        removePending(command);
        return;
      }
      if (
        reason instanceof ApiError &&
        reason.status === 401
      ) {
        loseSession();
        return;
      }
      if (reason instanceof ApiError && reason.status < 500) {
        setActionError(reason.message);
        removePending(command);
      } else {
        setRetryCommand(command);
        setActionError(
          "The result is unknown. You can retry this command safely.",
        );
      }
    }
  }

  function runAction(action: OpaqueActionDescriptor) {
    if (!view || !action.enabled || pendingByAction[action.actionId]) return;
    void executeCommand({
      commandId: crypto.randomUUID(),
      expectedRevision: view.revision,
      actionId: action.actionId,
    });
  }

  async function copyInvitation() {
    if (!session.inviteToken) return;
    try {
      await navigator.clipboard.writeText(
        makeInviteUrl(roomId, session.inviteToken),
      );
      setCopied(true);
      setActionError(null);
    } catch {
      setActionError("Could not copy the invitation. Check clipboard access.");
    }
  }

  if (!view) {
    return (
      <main className="page-shell loading-shell" aria-live="polite">
        <div className="loading-mark" aria-hidden="true">四</div>
        <p>Opening your room…</p>
        {connection.error && <p className="message error">{connection.error}</p>}
      </main>
    );
  }

  const invitationAction = view.actions.find(
    (action) => action.presentationSlot === "invitation",
  );
  const roomActions = view.actions.filter(
    (action) => action.presentationSlot === "roomActions",
  );
  const invitationPending = invitationAction
    ? pendingByAction[invitationAction.actionId]
    : undefined;

  return (
    <main className="page-shell lobby-shell">
      <header className="lobby-header">
        <BrandLink />
        <div className={`connection-status ${connection.status}`} role="status">
          <span aria-hidden="true" />
          {connection.status === "connected"
            ? "Live"
            : connection.status === "offline"
              ? "Offline"
              : connection.status === "connecting"
                ? "Connecting"
                : "Reconnecting"}
        </div>
      </header>

      <div className="lobby-title-row">
        <div>
          <p className="eyebrow">Private table · Revision {view.revision}</p>
          <h1>Room lobby</h1>
          <p>Settle in while the table fills. The host starts when everyone is ready.</p>
        </div>
        <span className="room-status">{view.status.replaceAll("_", " ")}</span>
      </div>

      <div className="lobby-layout">
        <div className="main-column">
          <section className="panel seats-panel" aria-labelledby="seats-heading">
            <div className="panel-heading">
              <div>
                <p className="step-label">Four-seat table</p>
                <h2 id="seats-heading">Players</h2>
              </div>
              <span>{view.seats.filter((seat) => seat.occupant).length}/4 seated</span>
            </div>
            <SeatList view={view} />
          </section>

          {view.status === "IN_MATCH" && view.game?.status === "PENDING_SETUP" && (
            <section className="panel setup-panel" aria-labelledby="setup-heading">
              <p className="step-label">Match created</p>
              <h2 id="setup-heading">Match started; gameplay arrives in Milestone 3</h2>
              <p>
                Gameplay is intentionally not available in this preview. The
                room roster and rules are now locked.
              </p>
            </section>
          )}

          <RulesCard view={view} />
        </div>

        <aside className="side-column">
          {invitationAction && view.status !== "IN_MATCH" && (
            <section className="panel invite-panel" aria-labelledby="invite-heading">
              <p className="step-label">Host invitation</p>
              <h2 id="invite-heading">
                {session.inviteToken ? "Invite players" : "Create an invitation link"}
              </h2>
              <p>
                {session.inviteToken
                  ? "Anyone with this private link can request an open seat."
                  : "This browser cannot recover the previous host’s private link. Create a new one to invite players."}
              </p>
              <div className="invite-actions">
                {session.inviteToken && (
                  <button className="secondary-action full-width" type="button" onClick={copyInvitation}>
                    {copied ? "Invitation copied" : "Copy invitation link"}
                  </button>
                )}
                <button
                  aria-describedby={
                    invitationAction.disabledReason
                      ? "invite-action-disabled-reason"
                      : undefined
                  }
                  className="secondary-action full-width"
                  type="button"
                  disabled={!invitationAction.enabled || Boolean(invitationPending)}
                  onClick={() => runAction(invitationAction)}
                >
                  {invitationPending ? "Working…" : invitationAction.label}
                </button>
              </div>
              <p className="fine-print">
                Creating a new invitation link invalidates every previous link.
              </p>
              {invitationAction.disabledReason && (
                <p className="disabled-reason" id="invite-action-disabled-reason">
                  {invitationAction.disabledReason}
                </p>
              )}
            </section>
          )}

          <section className="panel actions-panel" aria-labelledby="actions-heading">
            <p className="step-label">Available now</p>
            <h2 id="actions-heading">Room actions</h2>
            {roomActions.length === 0 ? (
              <p className="fine-print">No actions are available right now.</p>
            ) : (
              <div className="action-stack">
                {roomActions.map((action, index) => {
                  const reasonId = action.disabledReason
                    ? `action-disabled-reason-${index}`
                    : undefined;
                  return (
                    <div className="action-entry" key={action.actionId}>
                      <button
                        aria-describedby={reasonId}
                        className={`descriptor-action tone-${action.tone ?? "neutral"}`}
                        type="button"
                        disabled={!action.enabled || Boolean(pendingByAction[action.actionId])}
                        onClick={() => runAction(action)}
                      >
                        {pendingByAction[action.actionId] ? "Working…" : action.label}
                      </button>
                      {action.disabledReason && (
                        <p className="disabled-reason" id={reasonId}>
                          {action.disabledReason}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            {retryCommand && actionError && (
              <button className="retry-action" type="button" onClick={() => void executeCommand(retryCommand)}>
                Retry safely
              </button>
            )}
            {notice && <p className="message notice" role="status">{notice}</p>}
            {actionError && <p className="message error" role="alert">{actionError}</p>}
            {connection.error && !actionError && (
              <p className="message error" role="status">{connection.error}</p>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}

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
    <Lobby
      roomId={roomId}
      session={session}
      initialView={initialView}
      onSessionChange={setSession}
      onSessionValidated={() => setCapturedInviteToken(null)}
      onSessionLost={() => {
        setSession(null);
      }}
    />
  );
}

function NotFound() {
  return (
    <main className="page-shell narrow-shell">
      <BrandLink />
      <section className="entry-card lost-card">
        <h1>Page not found</h1>
        <Link className="primary-action link-action" to="/">
          Return home
        </Link>
      </section>
    </main>
  );
}

function RoomRoute() {
  const { roomId } = useParams();
  return roomId ? <RoomPage key={roomId} roomId={roomId} /> : <NotFound />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/rooms/:roomId" element={<RoomRoute />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
