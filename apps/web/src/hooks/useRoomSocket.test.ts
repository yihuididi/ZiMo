import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createSocketTicket,
  getRoom,
  ROOM_SOCKET_PROTOCOL,
  ROOM_SOCKET_TICKET_PREFIX,
} from "../lib/api";
import { roomView } from "../test/fixtures";
import { useRoomSocket } from "./useRoomSocket";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    getRoom: vi.fn(),
    createSocketTicket: vi.fn(),
    roomWebSocketUrl: vi.fn(() => "wss://api.example/rooms/room-a/ws"),
  };
});

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readonly protocols: string[];
  protocol = ROOM_SOCKET_PROTOCOL;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  close = vi.fn();

  constructor(url: string | URL, protocols?: string | string[]) {
    this.url = String(url);
    this.protocols = Array.isArray(protocols)
      ? protocols
      : protocols
        ? [protocols]
        : [];
    MockWebSocket.instances.push(this);
  }

  open() {
    this.onopen?.(new Event("open"));
  }

  message(value: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(value) }));
  }

  disconnect() {
    this.onclose?.(new CloseEvent("close"));
  }
}

let browserOnline = true;

describe("room live connection", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    browserOnline = true;
    vi.spyOn(window.navigator, "onLine", "get").mockImplementation(
      () => browserOnline,
    );
    vi.mocked(getRoom).mockReset();
    vi.mocked(createSocketTicket).mockReset();
  });

  afterEach(() => vi.useRealTimers());

  it("refetches and obtains a new single-use ticket on every reconnect", async () => {
    vi.useFakeTimers();
    vi.mocked(getRoom)
      .mockResolvedValueOnce(roomView({ revision: 7 }))
      .mockResolvedValueOnce(roomView({ revision: 8 }));
    vi.mocked(createSocketTicket)
      .mockResolvedValueOnce({ ticket: "ticket-one", expiresAtMs: 10_000 })
      .mockResolvedValueOnce({ ticket: "ticket-two", expiresAtMs: 20_000 });
    const onView = vi.fn();
    const onSessionEnded = vi.fn();

    const { result, unmount } = renderHook(() =>
      useRoomSocket({
        roomId: "room-a",
        playerToken: "player-secret",
        onView,
        onSessionEnded,
      }),
    );
    await act(async () => {});

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe(
      "wss://api.example/rooms/room-a/ws",
    );
    expect(MockWebSocket.instances[0].protocols).toEqual([
      ROOM_SOCKET_PROTOCOL,
      `${ROOM_SOCKET_TICKET_PREFIX}ticket-one`,
    ]);
    act(() => MockWebSocket.instances[0].open());
    expect(result.current.status).toBe("connected");

    act(() => MockWebSocket.instances[0].disconnect());
    expect(result.current.status).toBe("reconnecting");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    expect(getRoom).toHaveBeenCalledTimes(2);
    expect(createSocketTicket).toHaveBeenCalledTimes(2);
    expect(MockWebSocket.instances).toHaveLength(2);
    expect(MockWebSocket.instances[1].protocols[1]).toBe("ticket.ticket-two");
    expect(onView).toHaveBeenNthCalledWith(1, expect.objectContaining({ revision: 7 }));
    expect(onView).toHaveBeenNthCalledWith(2, expect.objectContaining({ revision: 8 }));

    unmount();
    expect(MockWebSocket.instances[1].close).toHaveBeenCalledWith(
      1000,
      "Page closed",
    );
    await vi.advanceTimersByTimeAsync(20_000);
    expect(createSocketTicket).toHaveBeenCalledTimes(2);
  });

  it("accepts only roomView frames for the current room", async () => {
    vi.mocked(getRoom).mockResolvedValue(roomView());
    vi.mocked(createSocketTicket).mockResolvedValue({
      ticket: "ticket-one",
      expiresAtMs: 10_000,
    });
    const onView = vi.fn();
    renderHook(() =>
      useRoomSocket({
        roomId: "room-a",
        playerToken: "player-secret",
        onView,
        onSessionEnded: vi.fn(),
      }),
    );
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    onView.mockClear();

    act(() => {
      MockWebSocket.instances[0].message({ type: "event", view: roomView() });
      MockWebSocket.instances[0].message({
        type: "roomView",
        view: roomView({ roomId: "another-room" }),
      });
      MockWebSocket.instances[0].message({
        type: "roomView",
        view: roomView({ revision: 9 }),
      });
    });

    expect(onView).toHaveBeenCalledTimes(1);
    expect(onView).toHaveBeenCalledWith(expect.objectContaining({ revision: 9 }));
  });

  it("ends the local session when authenticated refresh is rejected", async () => {
    vi.mocked(getRoom).mockRejectedValue(
      new ApiError(401, "UNAUTHORIZED", "Session expired"),
    );
    const onSessionEnded = vi.fn();
    renderHook(() =>
      useRoomSocket({
        roomId: "room-a",
        playerToken: "player-secret",
        onView: vi.fn(),
        onSessionEnded,
      }),
    );

    await waitFor(() => expect(onSessionEnded).toHaveBeenCalledOnce());
    expect(createSocketTicket).not.toHaveBeenCalled();
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("keeps the session and exposes a 403 without opening a socket", async () => {
    vi.mocked(getRoom).mockRejectedValue(
      new ApiError(403, "ORIGIN_FORBIDDEN", "Origin is not allowed"),
    );
    const onSessionEnded = vi.fn();
    const { result, unmount } = renderHook(() =>
      useRoomSocket({
        roomId: "room-a",
        playerToken: "player-secret",
        onView: vi.fn(),
        onSessionEnded,
      }),
    );

    await waitFor(() => expect(result.current.error).toBe("Origin is not allowed"));
    expect(onSessionEnded).not.toHaveBeenCalled();
    expect(createSocketTicket).not.toHaveBeenCalled();
    expect(MockWebSocket.instances).toHaveLength(0);
    unmount();
  });

  it("does not start an overlapping connection for duplicate online events", async () => {
    let resolveRefresh!: (view: ReturnType<typeof roomView>) => void;
    const pendingRefresh = new Promise<ReturnType<typeof roomView>>((resolve) => {
      resolveRefresh = resolve;
    });
    vi.mocked(getRoom).mockReturnValue(pendingRefresh);
    vi.mocked(createSocketTicket).mockResolvedValue({
      ticket: "ticket-one",
      expiresAtMs: 10_000,
    });

    const { unmount } = renderHook(() =>
      useRoomSocket({
        roomId: "room-a",
        playerToken: "player-secret",
        onView: vi.fn(),
        onSessionEnded: vi.fn(),
      }),
    );
    await waitFor(() => expect(getRoom).toHaveBeenCalledOnce());

    act(() => window.dispatchEvent(new Event("online")));
    expect(getRoom).toHaveBeenCalledOnce();

    await act(async () => resolveRefresh(roomView()));
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    expect(createSocketTicket).toHaveBeenCalledOnce();
    unmount();
  });

  it("invalidates an in-flight attempt offline and reconnects once online", async () => {
    let resolveStaleRefresh!: (view: ReturnType<typeof roomView>) => void;
    const staleRefresh = new Promise<ReturnType<typeof roomView>>((resolve) => {
      resolveStaleRefresh = resolve;
    });
    vi.mocked(getRoom)
      .mockReturnValueOnce(staleRefresh)
      .mockResolvedValueOnce(roomView({ revision: 8 }));
    vi.mocked(createSocketTicket).mockResolvedValue({
      ticket: "ticket-fresh",
      expiresAtMs: 20_000,
    });
    const onView = vi.fn();

    const { unmount } = renderHook(() =>
      useRoomSocket({
        roomId: "room-a",
        playerToken: "player-secret",
        onView,
        onSessionEnded: vi.fn(),
      }),
    );
    await waitFor(() => expect(getRoom).toHaveBeenCalledOnce());

    act(() => {
      browserOnline = false;
      window.dispatchEvent(new Event("offline"));
      browserOnline = true;
      window.dispatchEvent(new Event("online"));
    });
    await act(async () => resolveStaleRefresh(roomView({ revision: 7 })));

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    expect(getRoom).toHaveBeenCalledTimes(2);
    expect(createSocketTicket).toHaveBeenCalledOnce();
    expect(onView).toHaveBeenCalledTimes(1);
    expect(onView).toHaveBeenCalledWith(
      expect.objectContaining({ revision: 8 }),
    );
    unmount();
  });
});
