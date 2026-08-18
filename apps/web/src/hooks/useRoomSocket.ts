import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  createSocketTicket,
  getRoom,
  ROOM_SOCKET_PROTOCOL,
  ROOM_SOCKET_TICKET_PREFIX,
  roomWebSocketUrl,
} from "../lib/api";
import type { PublicRoomView, RoomSocketMessage } from "../lib/types";

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "offline";

const RETRY_DELAYS_MS = [500, 1_000, 2_000, 5_000, 10_000] as const;

interface UseRoomSocketOptions {
  roomId: string;
  playerToken: string;
  onView: (view: PublicRoomView) => void;
  onSessionEnded: () => void;
}

export function useRoomSocket({
  roomId,
  playerToken,
  onView,
  onSessionEnded,
}: UseRoomSocketOptions): {
  status: ConnectionStatus;
  error: string | null;
} {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const onViewRef = useRef(onView);
  const onSessionEndedRef = useRef(onSessionEnded);
  onViewRef.current = onView;
  onSessionEndedRef.current = onSessionEnded;

  useEffect(() => {
    let disposed = false;
    let attemptNumber = 0;
    let retryTimer: number | undefined;
    let socket: WebSocket | undefined;
    let requestController: AbortController | undefined;
    let connectionGeneration = 0;
    let connectInFlight = false;
    let reconnectRequested = false;

    const stopForLostSession = () => {
      if (disposed) return;
      disposed = true;
      onSessionEndedRef.current();
    };

    const scheduleReconnect = () => {
      if (disposed || retryTimer !== undefined) return;
      if (!navigator.onLine) {
        setStatus("offline");
        return;
      }
      setStatus("reconnecting");
      const delay =
        RETRY_DELAYS_MS[Math.min(attemptNumber, RETRY_DELAYS_MS.length - 1)];
      attemptNumber += 1;
      retryTimer = window.setTimeout(() => {
        retryTimer = undefined;
        void connect();
      }, delay);
    };

    const connect = async () => {
      if (disposed) return;
      if (socket !== undefined) return;
      if (connectInFlight) {
        reconnectRequested = true;
        return;
      }
      if (!navigator.onLine) {
        setStatus("offline");
        return;
      }
      connectInFlight = true;
      reconnectRequested = false;
      const generation = ++connectionGeneration;
      setStatus(attemptNumber === 0 ? "connecting" : "reconnecting");
      setError(null);
      requestController?.abort();
      const controller = new AbortController();
      requestController = controller;

      try {
        // Refresh first so every reconnect starts from an authoritative revision.
        const view = await getRoom(
          roomId,
          playerToken,
          controller.signal,
        );
        if (
          disposed ||
          generation !== connectionGeneration ||
          !navigator.onLine
        ) {
          return;
        }
        onViewRef.current(view);

        // Tickets are single-use; never reuse one across connection attempts.
        const { ticket } = await createSocketTicket(
          roomId,
          playerToken,
          controller.signal,
        );
        if (
          disposed ||
          generation !== connectionGeneration ||
          !navigator.onLine
        ) {
          return;
        }

        const candidate = new WebSocket(roomWebSocketUrl(roomId), [
          ROOM_SOCKET_PROTOCOL,
          `${ROOM_SOCKET_TICKET_PREFIX}${ticket}`,
        ]);
        socket = candidate;

        candidate.onopen = () => {
          if (disposed || socket !== candidate) return;
          if (candidate.protocol !== ROOM_SOCKET_PROTOCOL) {
            setError("The server selected an unexpected socket protocol.");
            candidate.close(1002, "Unexpected protocol");
            return;
          }
          attemptNumber = 0;
          setStatus("connected");
          setError(null);
        };

        candidate.onmessage = (event) => {
          if (
            disposed ||
            socket !== candidate ||
            typeof event.data !== "string"
          ) {
            return;
          }
          try {
            const message = JSON.parse(event.data) as Partial<RoomSocketMessage>;
            if (
              message.type === "roomView" &&
              message.view &&
              message.view.roomId === roomId
            ) {
              onViewRef.current(message.view);
            }
          } catch {
            // Ignore malformed or forward-version socket frames.
          }
        };

        candidate.onerror = () => {
          if (!disposed && socket === candidate) {
            setError("Live connection interrupted.");
          }
        };

        candidate.onclose = () => {
          if (socket !== candidate) return;
          socket = undefined;
          scheduleReconnect();
        };
      } catch (reason) {
        if (
          disposed ||
          generation !== connectionGeneration ||
          (reason instanceof DOMException && reason.name === "AbortError")
        ) {
          return;
        }
        if (
          reason instanceof ApiError &&
          reason.status === 401
        ) {
          stopForLostSession();
          return;
        }
        setError(
          reason instanceof Error
            ? reason.message
            : "Unable to establish a live connection.",
        );
        scheduleReconnect();
      } finally {
        if (requestController === controller) requestController = undefined;
        connectInFlight = false;
        if (
          reconnectRequested &&
          !disposed &&
          socket === undefined &&
          navigator.onLine
        ) {
          reconnectRequested = false;
          void connect();
        }
      }
    };

    const handleOffline = () => {
      if (disposed) return;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
        retryTimer = undefined;
      }
      setStatus("offline");
      connectionGeneration += 1;
      requestController?.abort();
      const currentSocket = socket;
      socket = undefined;
      currentSocket?.close();
    };

    const handleOnline = () => {
      if (disposed || retryTimer !== undefined) return;
      void connect();
    };

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    void connect();

    return () => {
      disposed = true;
      requestController?.abort();
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      try {
        socket?.close(1000, "Page closed");
      } catch {
        // Some test/browser implementations reject closing during CONNECTING.
      }
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, [roomId, playerToken]);

  return { status, error };
}
