import { useMemo } from "react";

import { BrandLink } from "../../../components/BrandLink";
import { PageHeading } from "../../../components/PageHeading";
import { useDocumentTitle } from "../../../hooks/useDocumentTitle";
import type { ConnectionStatus } from "../../../hooks/useRoomSocket";
import type {
  OpaqueActionDescriptor,
  OpponentSeatView,
  PublicRoomView,
  PublicSeatView,
  SelfSeatView,
} from "../../../lib/types";
import { CommandStatus } from "../CommandStatus";
import type {
  CommandFeedback,
  CommandOperation,
} from "../roomCommandReducer";
import { DisconnectedStatus } from "../lobby/DisconnectedStatus";
import { DiscardTile, TileBack, TileFace } from "./Tile";
import {
  bindTileActions,
  isGameplayPresentationSlot,
} from "./tileActionBindings";
import {
  formatDeadlineCountdown,
  useDeadlineCountdown,
} from "./useDeadlineCountdown";

export type TablePosition = "bottom" | "right" | "top" | "left";

const positions: readonly TablePosition[] = ["bottom", "right", "top", "left"];

export function positionSeats(
  seats: readonly PublicSeatView[],
): Record<TablePosition, PublicSeatView | null> {
  const positioned: Record<TablePosition, PublicSeatView | null> = {
    bottom: null,
    right: null,
    top: null,
    left: null,
  };
  const ownSeat = seats.find((seat): seat is SelfSeatView => seat.view === "self");
  if (!ownSeat) return positioned;

  for (const seat of seats) {
    const relativeSlot = (seat.slot - ownSeat.slot + 4) % 4;
    positioned[positions[relativeSlot]] = seat;
  }
  return positioned;
}

function occupantName(seat: PublicSeatView | null) {
  return seat?.occupant?.displayName ?? "Open seat";
}

function SeatHeader({
  seat,
  view,
}: {
  seat: PublicSeatView;
  view: PublicRoomView;
}) {
  const game = view.game;
  const player = seat.occupant?.playerId
    ? view.players.find((item) => item.playerId === seat.occupant?.playerId)
    : undefined;
  const isActive = game?.phase?.activeSeatId === seat.seatId;
  const isDealer = game?.dealerSeatId === seat.seatId;

  return (
    <div className="table-seat-heading">
      <div>
        <strong>{occupantName(seat)}</strong>
        <span>
          {seat.wind ? `${seat.wind[0]}${seat.wind.slice(1).toLowerCase()}` : "—"}
          {seat.occupant?.playerId === view.viewerPlayerId ? " · You" : ""}
          {seat.occupant?.controllerType === "automated" ? " · Bot" : ""}
        </span>
      </div>
      <div className="table-seat-chips">
        {isDealer && <span className="dealer-chip">Dealer</span>}
        {isActive && <span className="turn-chip">Active</span>}
        {player?.connectionStatus === "DISCONNECTED" && (
          <DisconnectedStatus
            disconnectExpiresAtMs={player.disconnectExpiresAtMs}
            serverTimeMs={view.serverTimeMs}
          />
        )}
      </div>
    </div>
  );
}

function BonusTiles({ seat }: { seat: PublicSeatView }) {
  if (seat.bonusTiles.length === 0) {
    return <span className="table-no-bonuses">No bonuses exposed</span>;
  }
  return (
    <div className="table-bonuses" aria-label={`${occupantName(seat)} exposed bonuses`}>
      {seat.bonusTiles.map((tile, index) => (
        <TileFace tile={tile} size="mini" key={`${tile.face.family}-${tile.face.value}-${index}`} />
      ))}
    </div>
  );
}

function Melds({ seat, view }: { seat: PublicSeatView; view: PublicRoomView }) {
  if (seat.melds.length === 0) return null;
  return <div className="table-melds" aria-label={`${occupantName(seat)} melds`}>
    {seat.melds.map((meld, index) => <div className="table-meld" key={index}>
      <span>{meld.visibility === "exposed" && meld.kongKind ? meld.kongKind.replace("_", "-") : meld.kind}</span>
      <div className="table-meld-tiles">
        {meld.visibility === "exposed"
          ? meld.tiles.map((tile, i) => <TileFace key={i} tile={tile} size="mini" />)
          : Array.from({ length: meld.tileCount }, (_, i) => <TileBack key={i} />)}
      </div>
      {meld.visibility === "exposed" && meld.discardSequence !== null && <small>
        From {occupantName(view.seats.find(s => s.seatId === meld.claimedFromSeatId) ?? null)} · #{meld.discardSequence}
      </small>}
    </div>)}
  </div>;
}

function OpponentHand({ seat }: { seat: OpponentSeatView }) {
  const description = `${seat.concealedTileCount} concealed tiles${
    seat.hasDrawnTile ? " and a separate drawn tile" : ""
  }`;
  return (
    <div className="opponent-hand" aria-label={description}>
      <div className="opponent-tile-backs" aria-hidden="true">
        {Array.from({ length: seat.concealedTileCount }, (_, index) => (
          <TileBack key={index} />
        ))}
        {seat.hasDrawnTile && <TileBack separated />}
      </div>
      <span className="sr-only">{description}</span>
    </div>
  );
}

function TableSeat({
  seat,
  position,
  view,
}: {
  seat: PublicSeatView | null;
  position: Exclude<TablePosition, "bottom">;
  view: PublicRoomView;
}) {
  if (!seat) return <section className={`table-seat table-seat-${position}`} />;
  return (
    <section
      className={`table-seat table-seat-${position}`}
      aria-label={`${occupantName(seat)}, ${position} seat`}
    >
      <SeatHeader seat={seat} view={view} />
      {seat.view === "opponent" && <OpponentHand seat={seat} />}
      <BonusTiles seat={seat} />
      <Melds seat={seat} view={view} />
    </section>
  );
}

function DiscardRiver({ view }: { view: PublicRoomView }) {
  const discards = view.game?.discards ?? [];
  const seatsById = new Map(view.seats.map((seat) => [seat.seatId, seat]));
  return (
    <section className="discard-river" aria-labelledby="discards-heading">
      <div className="table-center-heading">
        <h2 id="discards-heading">Discards</h2>
        <span>{discards.length} played</span>
      </div>
      {discards.length === 0 ? (
        <p className="empty-river">The table is waiting for its first discard.</p>
      ) : (
        <ol className="discard-grid">
          {discards.map((discard) => {
            const discarder = seatsById.get(discard.discardedBySeatId);
            return (
              <li key={discard.sequence}>
                <span className="discard-sequence">#{discard.sequence}</span>
                <TileFace tile={discard.tile} size="mini" />
                {discard.claimedBySeatId && <small className="discard-claimed">
                  {discard.claimKind} · {occupantName(seatsById.get(discard.claimedBySeatId) ?? null)}
                </small>}
                <span className="sr-only">
                  discarded by {occupantName(discarder ?? null)}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function PhaseStatus({ view }: { view: PublicRoomView }) {
  const phase = view.game?.phase;
  const countdown = useDeadlineCountdown({
    deadlineMs: view.deadlineMs,
    serverTimeMs: view.serverTimeMs,
    windowId: view.windowId,
  });
  const activeSeat = phase?.activeSeatId
    ? view.seats.find((seat) => seat.seatId === phase.activeSeatId)
    : null;

  if (view.game?.status === "FINISHED") {
    const result = view.game.result;
    const winner = view.seats.find(seat => seat.seatId === result?.winnerSeatId);
    return (
      <div className="phase-status phase-finished" role="status">
        <strong>{result?.outcome === "WIN" ? `${winner ? occupantName(winner) : "Player"} wins` : "Hand tied"}</strong>
        <span>{result?.outcome === "WIN" ? `${result.cappedFan} capped fan` : "The live wall is exhausted."}</span>
      </div>
    );
  }

  if ((phase?.type === "discardClaims" || phase?.type === "kongRobbery") && view.deadlineMs !== null) {
    return (
      <div className="phase-status phase-window">
        <span>{phase.type === "kongRobbery" ? "Kong-1 may be robbed for Game." : "Every discard rests for the full claim window."}</span>
        <strong role="timer" aria-label={phase.type === "kongRobbery" ? "Robbery window countdown" : "Discard window countdown"}>
          {countdown.resolving
            ? "Resolving…"
            : countdown.remainingMs === null
              ? "—"
              : formatDeadlineCountdown(countdown.remainingMs)}
        </strong>
      </div>
    );
  }

  if (activeSeat) {
    return (
      <div className="phase-status" role="status">
        <strong>
          {activeSeat.occupant?.playerId === view.viewerPlayerId
            ? "Your turn"
            : `${occupantName(activeSeat)}’s turn`}
        </strong>
        <span>
          {phase?.type === "awaitingDiscard"
            ? "Choose a tile to discard."
            : phase?.type === "finalTileDecision"
              ? "Last playable tile. Choose a Kong or finish the hand; no replacement is taken."
              : "Drawing from the live wall."}
        </span>
      </div>
    );
  }

  return (
    <div className="phase-status" role="status">
      <strong>Table in progress</strong>
      <span>Waiting for the next authoritative update.</span>
    </div>
  );
}

interface TableViewProps {
  view: PublicRoomView;
  connection: { status: ConnectionStatus; error: string | null };
  roomWarning: string | null;
  operationsByActionId: Record<string, CommandOperation>;
  recoverableOperations: Array<
    Extract<CommandOperation, { phase: "retryable" }>
  >;
  feedback: CommandFeedback[];
  onRunAction: (action: OpaqueActionDescriptor) => void;
  onRetryAction: (actionId: string) => void;
}

export function TableView({
  view,
  connection,
  roomWarning,
  operationsByActionId,
  recoverableOperations,
  feedback,
  onRunAction,
  onRetryAction,
}: TableViewProps) {
  const selfSeat = view.seats.find(
    (seat): seat is SelfSeatView => seat.view === "self",
  );
  const positioned = useMemo(() => positionSeats(view.seats), [view.seats]);
  const bindings = bindTileActions(
    view.actions,
    selfSeat?.concealedTiles.length ?? 0,
    selfSeat?.drawnTile !== null && selfSeat?.drawnTile !== undefined,
  );
  const gameplayOperations = Object.values(operationsByActionId).filter(
    (operation) => isGameplayPresentationSlot(operation.slot),
  );
  const groupLocked = gameplayOperations.length > 0;
  const claimCountdown = useDeadlineCountdown({ deadlineMs: view.deadlineMs, serverTimeMs: view.serverTimeMs, windowId: view.windowId });
  const choiceActions = view.actions.filter(action => action.presentationSlot === "claimActions" || action.presentationSlot === "turnActions");
  const hasDiscardActions = view.actions.some((action) =>
    isGameplayPresentationSlot(action.presentationSlot),
  );
  const hasCommandStatus =
    recoverableOperations.length > 0 ||
    feedback.length > 0 ||
    roomWarning !== null ||
    connection.error !== null;
  useDocumentTitle(
    hasDiscardActions
      ? "Your turn · ZiMo Mahjong"
      : view.game?.status === "FINISHED"
        ? "Hand complete · ZiMo Mahjong"
        : "Mahjong table · ZiMo Mahjong",
  );

  return (
    <main className="page-shell table-shell">
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

      <div className="table-title-row">
        <div>
          <p>Singapore ruleset · Revision {view.revision}</p>
          <PageHeading focusOnMount>Mahjong table</PageHeading>
        </div>
        <div className="wall-summary" aria-label="Wall tile counts">
          <span>Live wall <strong>{view.game?.liveWallTileCount ?? 0}</strong></span>
          <span>Reserve <strong>{view.game?.reserveWallTileCount ?? 0}</strong></span>
          <span>Prevailing <strong>{view.game?.prevailingWind ?? "EAST"}</strong></span>
        </div>
      </div>

      <aside className="preview-notice" aria-label="Preview limitations">
        <strong>One-hand preview</strong>
        <span>Game and fan are available. Payments, editable settings, and additional hands are coming later.</span>
      </aside>

      <PhaseStatus view={view} />
      {view.game?.status === "FINISHED" && view.game.result?.outcome === "WIN" && (
        <section className="panel fan-result" aria-label="Winning fan breakdown">
          <h2>Winning hand</h2>
          <p>{view.game.result.winSource === "SELF_DRAW" ? "Self draw" : view.game.result.winSource === "ROBBED_KONG" ? "Robbed Kong-1" : "Discard Game"} · {view.game.result.fan} raw fan · {view.game.result.cappedFan} capped fan</p>
          <ul>{view.game.result.fanAwards.map((award, index) => (
            <li key={`${award.name}-${index}`}><span>{award.name}</span><strong>{award.fan}</strong></li>
          ))}</ul>
        </section>
      )}
      {(choiceActions.length > 0 || view.game?.ownClaimSubmitted) && (
        <section className="table-choices" aria-label="Table choices">
          {view.game?.ownClaimSubmitted
            ? <p role="status">Choice recorded. Waiting for the window to close.</p>
            : <div className="table-choice-buttons">
              {choiceActions.map(action => <button
                type="button" key={action.actionId}
                disabled={!action.enabled || groupLocked || (action.presentationSlot === "claimActions" && claimCountdown.resolving)}
                onClick={() => onRunAction(action)}
              >
                <strong>{action.label}</strong>
                <span className="table-choice-tiles">{action.tiles?.map((tile, index) => <TileFace key={index} tile={tile} size="mini" />)}</span>
              </button>)}
            </div>}
        </section>
      )}

      <div className="table-stage">
        <TableSeat seat={positioned.top} position="top" view={view} />
        <TableSeat seat={positioned.left} position="left" view={view} />
        <DiscardRiver view={view} />
        <TableSeat seat={positioned.right} position="right" view={view} />

        <section className="table-seat table-seat-bottom" aria-label="Your seat, bottom seat">
          {selfSeat && <SeatHeader seat={selfSeat} view={view} />}
          {selfSeat && <BonusTiles seat={selfSeat} />}
          {selfSeat && <Melds seat={selfSeat} view={view} />}
          {selfSeat && (
            <div className="own-hand-area">
              <div className="own-hand-copy">
                <strong>Your hand</strong>
                <span>Server sorted · drawn tile stays separate</span>
              </div>
              <div className="own-hand" role="group" aria-label="Your concealed hand">
                {selfSeat.concealedTiles.map((tile, index) => (
                  <DiscardTile
                    tile={tile}
                    action={bindings.concealed.get(index)}
                    actionsValid={bindings.valid}
                    groupLocked={groupLocked}
                    onRunAction={onRunAction}
                    key={`${tile.face.family}-${tile.face.value}-${index}`}
                  />
                ))}
                {selfSeat.drawnTile && (
                  <DiscardTile
                    tile={selfSeat.drawnTile}
                    action={bindings.drawn ?? undefined}
                    actionsValid={bindings.valid}
                    groupLocked={groupLocked}
                    onRunAction={onRunAction}
                    separated
                  />
                )}
              </div>
              {!bindings.valid && (
                <p className="message error" role="alert">
                  Discard choices are refreshing. Wait for the next table update.
                </p>
              )}
              {groupLocked && (
                <p className="hand-lock-message" role="status">
                  {gameplayOperations.some((operation) => operation.phase === "retryable")
                    ? "The discard result is unknown. Retry it safely below."
                    : "Submitting your discard…"}
                </p>
              )}
            </div>
          )}
        </section>
      </div>

      {hasCommandStatus && (
        <section className="panel table-command-panel" aria-label="Table messages">
          <CommandStatus
            recoverableOperations={recoverableOperations}
            feedback={feedback}
            roomWarning={roomWarning}
            connectionError={connection.error}
            connectionStatus={connection.status}
            onRetryAction={onRetryAction}
          />
        </section>
      )}
    </main>
  );
}
