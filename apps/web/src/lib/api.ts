import type {
  CommandResponse,
  CreateRoomResponse,
  EventsResponse,
  GameConfig,
  PublicRoomView,
  RoomCredentialsResponse,
  SocketTicketResponse,
} from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export const ROOM_SOCKET_PROTOCOL = "mahjong.v1";
export const ROOM_SOCKET_TICKET_PREFIX = "ticket.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly currentRevision?: number;

  constructor(
    status: number,
    code: string,
    message: string,
    currentRevision?: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.currentRevision = currentRevision;
  }
}

interface ErrorEnvelope {
  error?: {
    code?: unknown;
    message?: unknown;
    currentRevision?: unknown;
  };
}

interface RequestOptions extends Omit<RequestInit, "headers"> {
  token?: string;
}

async function requestJson<T>(
  path: string,
  { token, ...init }: RequestOptions = {},
): Promise<T> {
  const headers = new Headers({ Accept: "application/json" });
  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    credentials: "omit",
  });

  if (!response.ok) {
    let envelope: ErrorEnvelope = {};
    try {
      envelope = (await response.json()) as ErrorEnvelope;
    } catch {
      // The status remains useful if an intermediary returned a non-JSON body.
    }
    const code =
      typeof envelope.error?.code === "string"
        ? envelope.error.code
        : "HTTP_ERROR";
    const message =
      typeof envelope.error?.message === "string"
        ? envelope.error.message
        : `Request failed (HTTP ${response.status})`;
    const currentRevision =
      typeof envelope.error?.currentRevision === "number"
        ? envelope.error.currentRevision
        : undefined;
    throw new ApiError(response.status, code, message, currentRevision);
  }

  return (await response.json()) as T;
}

const roomPath = (roomId: string) => `/rooms/${encodeURIComponent(roomId)}`;

export function createRoom(
  displayName: string,
  signal?: AbortSignal,
): Promise<CreateRoomResponse> {
  return requestJson("/rooms", {
    method: "POST",
    body: JSON.stringify({ displayName }),
    signal,
  });
}

export function joinRoom(
  roomId: string,
  inviteToken: string,
  displayName: string,
  signal?: AbortSignal,
): Promise<RoomCredentialsResponse> {
  return requestJson(`${roomPath(roomId)}/join`, {
    method: "POST",
    body: JSON.stringify({ inviteToken, displayName }),
    signal,
  });
}

export function getRoom(
  roomId: string,
  playerToken: string,
  signal?: AbortSignal,
): Promise<PublicRoomView> {
  return requestJson(roomPath(roomId), {
    token: playerToken,
    signal,
  });
}

export function submitCommand(
  roomId: string,
  playerToken: string,
  command: {
    commandId: string;
    expectedRevision: number;
    actionId: string;
  },
  signal?: AbortSignal,
): Promise<CommandResponse> {
  return requestJson(`${roomPath(roomId)}/commands`, {
    method: "POST",
    token: playerToken,
    body: JSON.stringify(command),
    signal,
  });
}

export function updateConfig(
  roomId: string,
  playerToken: string,
  expectedRevision: number,
  config: GameConfig,
  signal?: AbortSignal,
): Promise<Extract<CommandResponse, { type: "view" }>> {
  return requestJson(`${roomPath(roomId)}/config`, {
    method: "PATCH",
    token: playerToken,
    body: JSON.stringify({ expectedRevision, config }),
    signal,
  });
}

export function getEvents(
  roomId: string,
  playerToken: string,
  afterSequence?: number,
  signal?: AbortSignal,
): Promise<EventsResponse> {
  const query =
    afterSequence === undefined
      ? ""
      : `?afterSequence=${encodeURIComponent(afterSequence)}`;
  return requestJson(`${roomPath(roomId)}/events${query}`, {
    token: playerToken,
    signal,
  });
}

export function createSocketTicket(
  roomId: string,
  playerToken: string,
  signal?: AbortSignal,
): Promise<SocketTicketResponse> {
  return requestJson(`${roomPath(roomId)}/socket-ticket`, {
    method: "POST",
    token: playerToken,
    signal,
  });
}

export function roomWebSocketUrl(roomId: string): string {
  const url = new URL(
    `${apiBaseUrl}${roomPath(roomId)}/ws`,
    window.location.origin,
  );
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
