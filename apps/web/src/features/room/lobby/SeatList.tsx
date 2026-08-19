import { useMemo } from "react";

import type { PublicRoomView, PublicSeatView } from "../../../lib/types";
import { DisconnectedStatus } from "./DisconnectedStatus";

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

export function SeatList({ view }: { view: PublicRoomView }) {
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
          <li
            className={seat.occupant ? "seat occupied" : "seat empty"}
            key={seat.seatId}
          >
            <div className="seat-number" aria-hidden="true">
              {seat.slot + 1}
            </div>
            <div className="seat-copy">
              <strong>
                <span className="sr-only">Seat {seat.slot + 1}: </span>
                {occupant.name}
              </strong>
              <span>
                {seat.wind ? `${seat.wind} · ` : ""}
                {occupant.kind}
              </span>
            </div>
            {(occupant.ready !== null ||
              player?.connectionStatus === "DISCONNECTED") && (
              <div className="seat-statuses">
                {occupant.ready !== null && (
                  <span
                    className={
                      occupant.ready ? "ready-chip" : "waiting-chip"
                    }
                  >
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
