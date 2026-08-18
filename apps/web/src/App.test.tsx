import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import {
  ApiError,
  createRoom,
  getRoom,
  joinRoom,
  submitCommand,
} from "./lib/api";
import { loadRoomSession, saveRoomSession } from "./lib/session";
import type { PublicRoomView } from "./lib/types";
import { roomView } from "./test/fixtures";

const socketHarness = vi.hoisted(() => ({ options: null as unknown }));

vi.mock("./hooks/useRoomSocket", () => ({
  useRoomSocket: vi.fn((options: unknown) => {
    socketHarness.options = options;
    return { status: "connected", error: null };
  }),
}));

vi.mock("./lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./lib/api")>();
  return {
    ...actual,
    createRoom: vi.fn(),
    getRoom: vi.fn(),
    joinRoom: vi.fn(),
    submitCommand: vi.fn(),
  };
});

function emitSocketView(view: PublicRoomView) {
  const options = socketHarness.options as {
    onView: (incoming: PublicRoomView) => void;
  };
  act(() => options.onView(view));
}

function openHostLobby(view = roomView()) {
  saveRoomSession({
    version: 1,
    roomId: "room-a",
    playerId: "player-host",
    playerToken: "host-secret",
    inviteToken: "invite-original",
  });
  history.replaceState(null, "", "/rooms/room-a");
  const result = render(<App />);
  emitSocketView(view);
  return result;
}

function openMemberLobby() {
  const base = roomView();
  const memberView = roomView({
    viewerPlayerId: "player-member",
    players: [
      {
        playerId: "player-member",
        displayName: "Wei",
        role: "MEMBER",
        ready: false,
        connectionStatus: "CONNECTED",
        disconnectExpiresAtMs: null,
      },
    ],
    seats: base.seats.map((seat) =>
      seat.slot === 0 && seat.occupant
        ? {
            ...seat,
            occupant: {
              ...seat.occupant,
              displayName: "Wei",
              playerId: "player-member",
              role: "MEMBER" as const,
            },
          }
        : seat,
    ),
    actions: [
      {
        actionId: "opaque-member-ready",
        label: "Ready",
        enabled: true,
        tone: "primary",
        disabledReason: null,
        presentationSlot: "roomActions",
      },
    ],
  });
  saveRoomSession({
    version: 1,
    roomId: "room-a",
    playerId: "player-member",
    playerToken: "member-secret",
  });
  history.replaceState(null, "", "/rooms/room-a");
  render(<App />);
  emitSocketView(memberView);
}

function openPromotedHostLobby() {
  const base = roomView();
  const promotedView = roomView({
    viewerPlayerId: "player-member",
    players: [
      {
        playerId: "player-member",
        displayName: "Wei",
        role: "HOST",
        ready: false,
        connectionStatus: "CONNECTED",
        disconnectExpiresAtMs: null,
      },
    ],
    seats: base.seats.map((seat) =>
      seat.slot === 0 && seat.occupant
        ? {
            ...seat,
            occupant: {
              ...seat.occupant,
              displayName: "Wei",
              playerId: "player-member",
              role: "HOST" as const,
            },
          }
        : seat,
    ),
  });
  saveRoomSession({
    version: 1,
    roomId: "room-a",
    playerId: "player-member",
    playerToken: "member-secret",
  });
  history.replaceState(null, "", "/rooms/room-a");
  render(<App />);
  emitSocketView(promotedView);
  return promotedView;
}

function viewWithDisconnectedMember({
  disconnectExpiresAtMs = 1_700_000_300_000,
  presenceVersion = 1,
  revision = 7,
  serverTimeMs = 1_700_000_000_000,
  status = "WAITING_FOR_PLAYERS" as const,
}: {
  disconnectExpiresAtMs?: number | null;
  presenceVersion?: number;
  revision?: number;
  serverTimeMs?: number;
  status?: PublicRoomView["status"];
} = {}) {
  const base = roomView();
  return roomView({
    presenceVersion,
    revision,
    serverTimeMs,
    status,
    players: [
      ...base.players,
      {
        playerId: "player-member",
        displayName: "Wei",
        role: "MEMBER",
        ready: false,
        connectionStatus: "DISCONNECTED",
        disconnectExpiresAtMs,
      },
    ],
    seats: base.seats.map((seat) =>
      seat.slot === 1
        ? {
            ...seat,
            occupant: {
              controllerType: "external" as const,
              displayName: "Wei",
              playerId: "player-member",
              role: "MEMBER" as const,
              ready: false,
            },
          }
        : seat,
    ),
  });
}

describe("Milestone 2 room UI", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    history.replaceState(null, "", "/");
    socketHarness.options = null;
    vi.mocked(createRoom).mockReset();
    vi.mocked(joinRoom).mockReset();
    vi.mocked(getRoom).mockReset();
    vi.mocked(submitCommand).mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    Object.defineProperty(globalThis, "crypto", {
      configurable: true,
      value: { randomUUID: vi.fn(() => "00000000-0000-4000-8000-000000000001") },
    });
  });

  it("creates a host session scoped to the returned room", async () => {
    vi.mocked(createRoom).mockResolvedValue({
      roomId: "room-a",
      playerId: "player-host",
      playerToken: "host-secret",
      inviteToken: "invite-secret",
      view: roomView(),
    });
    render(<App />);

    fireEvent.change(screen.getByLabelText("Your display name"), {
      target: { value: "Mei" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create private room" }));

    await waitFor(() => expect(location.pathname).toBe("/rooms/room-a"));
    expect(createRoom).toHaveBeenCalledWith("Mei");
    expect(loadRoomSession("room-a")).toEqual({
      version: 1,
      roomId: "room-a",
      playerId: "player-host",
      playerToken: "host-secret",
      inviteToken: "invite-secret",
    });
  });

  it("reports when a newly issued capability cannot be stored", async () => {
    vi.mocked(createRoom).mockResolvedValue({
      roomId: "room-a",
      playerId: "player-host",
      playerToken: "host-secret",
      inviteToken: "invite-secret",
      view: roomView(),
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(() => {
      throw new DOMException("Storage denied", "SecurityError");
    });
    render(<App />);

    fireEvent.change(screen.getByLabelText("Your display name"), {
      target: { value: "Mei" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create private room" }));

    expect(
      await screen.findByText(/new room credentials could not be retained/i),
    ).toBeVisible();
    expect(location.pathname).toBe("/");
    expect(loadRoomSession("room-a")).toBeNull();
  });

  it("offers a saved room after tab storage is cleared and rejoins the same player", () => {
    saveRoomSession({
      version: 1,
      roomId: "room-a",
      playerId: "player-host",
      playerToken: "host-secret",
      inviteToken: "invite-secret",
    });
    sessionStorage.clear();
    render(<App />);

    const rejoin = screen.getByRole("link", { name: "Rejoin room room-a" });
    expect(rejoin).toBeVisible();
    expect(document.body).not.toHaveTextContent("host-secret");
    fireEvent.click(rejoin);

    expect(location.pathname).toBe("/rooms/room-a");
    expect(socketHarness.options).toMatchObject({
      roomId: "room-a",
      playerToken: "host-secret",
    });
  });

  it("opens a pasted invitation, scrubs its fragment, and joins by body", async () => {
    vi.mocked(joinRoom).mockResolvedValue({
      roomId: "room-a",
      playerId: "player-member",
      playerToken: "member-secret",
      view: roomView({ viewerPlayerId: "player-member" }),
    });
    render(<App />);

    fireEvent.change(screen.getByLabelText("Already invited?"), {
      target: {
        value: "https://mahjong.example/rooms/room-a#invite=invite-secret",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Open" }));

    expect(await screen.findByRole("heading", { name: "Join the table" })).toBeVisible();
    expect(location.pathname).toBe("/rooms/room-a");
    expect(location.hash).toBe("");

    fireEvent.change(screen.getByLabelText("Your display name"), {
      target: { value: "Wei" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Take a seat" }));

    expect(await screen.findByRole("heading", { name: "Room lobby" })).toBeVisible();
    expect(joinRoom).toHaveBeenCalledWith("room-a", "invite-secret", "Wei");
    expect(loadRoomSession("room-a")?.playerToken).toBe("member-secret");
    expect(loadRoomSession("room-a")?.inviteToken).toBeUndefined();
  });

  it("falls back to a fresh invitation when saved player access is revoked", () => {
    saveRoomSession({
      version: 1,
      roomId: "room-a",
      playerId: "stale-player",
      playerToken: "stale-secret",
    });
    history.replaceState(null, "", "/rooms/room-a#invite=fresh-invite");
    render(<App />);

    expect(location.hash).toBe("");
    const options = socketHarness.options as { onSessionEnded: () => void };
    act(() => options.onSessionEnded());

    expect(
      screen.getByRole("heading", { name: "Join the table" }),
    ).toBeVisible();
    expect(loadRoomSession("room-a")).toBeNull();
  });

  it("makes room-ID-only access an explicit unrecoverable session screen", () => {
    history.replaceState(null, "", "/rooms/known-room");
    render(<App />);
    expect(
      screen.getByRole("heading", { name: "This room session is unavailable" }),
    ).toBeVisible();
    expect(screen.getByText(/No valid player access/i)).toBeVisible();
  });

  it("orders seats by server slot and renders identity/readiness", () => {
    openHostLobby();
    const seats = screen.getAllByRole("listitem");
    expect(seats.map((seat) => seat.querySelector("strong")?.textContent)).toEqual([
      "Mei",
      "Open seat",
      "Bot Bamboo",
      "Open seat",
    ]);
    expect(screen.getByText("You · Host")).toBeVisible();
    expect(screen.getByText("Bot", { exact: true })).toBeVisible();
    expect(screen.getByText("Read only")).toBeVisible();
    expect(screen.getByText("1–5 fan")).toBeVisible();
  });

  it("shows a server-anchored removal countdown for a disconnected player", () => {
    vi.useFakeTimers();
    openHostLobby(viewWithDisconnectedMember());

    const tag = screen.getByText("Disconnected");
    expect(tag).toBeVisible();
    expect(tag.closest('[role="status"]')).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("Removing in 5:00")).toBeVisible();

    act(() => vi.advanceTimersByTime(1_000));
    expect(screen.getByText("Removing in 4:59")).toBeVisible();

    act(() => vi.advanceTimersByTime(299_000));
    expect(screen.getByText("Removing…")).toBeVisible();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("removes disconnected state and its timer when the player reconnects", () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    const disconnected = viewWithDisconnectedMember();
    openHostLobby(disconnected);
    expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    const presenceTimer = setIntervalSpy.mock.results[0]?.value;

    emitSocketView({
      ...disconnected,
      revision: 8,
      serverTimeMs: disconnected.serverTimeMs + 1_000,
      players: disconnected.players.map((player) =>
        player.playerId === "player-member"
          ? {
              ...player,
              connectionStatus: "CONNECTED" as const,
              disconnectExpiresAtMs: null,
            }
          : player,
      ),
    });

    expect(screen.queryByText("Disconnected")).not.toBeInTheDocument();
    expect(screen.queryByText(/Removing/)).not.toBeInTheDocument();
    expect(clearIntervalSpy).toHaveBeenCalledWith(presenceTimer);
  });

  it("shows a disconnected tag without a removal timer after match start", () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    openHostLobby(
      viewWithDisconnectedMember({
        disconnectExpiresAtMs: null,
        status: "IN_MATCH",
      }),
    );

    expect(screen.getByText("Disconnected")).toBeVisible();
    expect(screen.queryByText(/Removing/)).not.toBeInTheDocument();
    expect(setIntervalSpy).not.toHaveBeenCalled();
  });

  it("cleans up a pending disconnect countdown when the lobby unmounts", () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    const { unmount } = openHostLobby(viewWithDisconnectedMember());
    expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    const presenceTimer = setIntervalSpy.mock.results[0]?.value;

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalledWith(presenceTimer);
  });

  it("renders a member only from its individualized view and retained session", () => {
    openMemberLobby();

    expect(screen.getByText("You", { exact: true })).toBeVisible();
    expect(screen.queryByText("You · Host")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy invitation link" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ready" })).toBeEnabled();
    expect(
      screen.queryByRole("button", { name: "Create New Invitation Link" }),
    ).not.toBeInTheDocument();
  });

  it("lets a promoted host generate and then copy a new invitation", async () => {
    const promotedView = openPromotedHostLobby();
    vi.mocked(submitCommand).mockResolvedValue({
      type: "view",
      view: roomView({
        ...promotedView,
        revision: 8,
      }),
      inviteToken: "invite-promoted-host",
    });

    expect(
      screen.getByRole("heading", { name: "Create an invitation link" }),
    ).toBeVisible();
    expect(screen.getByText(/cannot recover the previous host/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Copy invitation link" })).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Create New Invitation Link" }),
    );

    await waitFor(() =>
      expect(submitCommand).toHaveBeenCalledWith("room-a", "member-secret", {
        commandId: "00000000-0000-4000-8000-000000000001",
        expectedRevision: 7,
        actionId: "opaque-rotate-id",
      }),
    );
    expect(loadRoomSession("room-a")?.inviteToken).toBe("invite-promoted-host");

    fireEvent.click(
      await screen.findByRole("button", { name: "Copy invitation link" }),
    );
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "http://localhost:3000/rooms/room-a#invite=invite-promoted-host",
      ),
    );
  });

  it("purges a former host invitation and ignores a delayed rotation result", async () => {
    let resolveRotation!: (
      value: Awaited<ReturnType<typeof submitCommand>>,
    ) => void;
    vi.mocked(submitCommand).mockReturnValue(
      new Promise((resolve) => {
        resolveRotation = resolve;
      }),
    );
    const base = roomView();
    openHostLobby(base);

    fireEvent.click(
      screen.getByRole("button", { name: "Create New Invitation Link" }),
    );
    await waitFor(() => expect(submitCommand).toHaveBeenCalledOnce());

    emitSocketView(
      roomView({
        revision: 8,
        presenceVersion: 1,
        viewerPlayerId: "player-host",
        players: [
          {
            playerId: "player-host",
            displayName: "Mei",
            role: "MEMBER",
            ready: false,
            connectionStatus: "DISCONNECTED",
            disconnectExpiresAtMs: 1_700_000_300_000,
          },
          {
            playerId: "player-next",
            displayName: "Wei",
            role: "HOST",
            ready: false,
            connectionStatus: "CONNECTED",
            disconnectExpiresAtMs: null,
          },
        ],
        actions: [
          {
            actionId: "opaque-leave-id",
            label: "Leave Room",
            enabled: true,
            tone: "danger",
            disabledReason: null,
            presentationSlot: "roomActions",
          },
        ],
      }),
    );

    await waitFor(() =>
      expect(loadRoomSession("room-a")?.inviteToken).toBeUndefined(),
    );
    expect(
      screen.queryByRole("button", { name: "Copy invitation link" }),
    ).not.toBeInTheDocument();

    await act(async () => {
      resolveRotation({
        type: "view",
        view: roomView({ revision: 7 }),
        inviteToken: "stale-rotated-invite",
      });
    });

    expect(loadRoomSession("room-a")?.inviteToken).toBeUndefined();
    expect(
      screen.queryByRole("button", { name: "Copy invitation link" }),
    ).not.toBeInTheDocument();
  });

  it("warns when browser storage blocks complete former-host invite removal", async () => {
    openHostLobby();
    sessionStorage.setItem(
      "mahjong.room.room-a.session",
      JSON.stringify({
        version: 1,
        roomId: "room-a",
        playerId: "player-host",
        playerToken: "host-secret",
        inviteToken: "legacy-invite",
        savedAtMs: 1,
      }),
    );
    const originalRemoveItem = Storage.prototype.removeItem;
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(function (
      this: Storage,
      key: string,
    ) {
      if (this === sessionStorage) {
        throw new DOMException("Storage denied", "SecurityError");
      }
      return originalRemoveItem.call(this, key);
    });

    emitSocketView(
      roomView({
        revision: 8,
        viewerPlayerId: "player-host",
        players: [
          {
            playerId: "player-host",
            displayName: "Mei",
            role: "MEMBER",
            ready: false,
            connectionStatus: "DISCONNECTED",
            disconnectExpiresAtMs: 1_700_000_300_000,
          },
          {
            playerId: "player-next",
            displayName: "Wei",
            role: "HOST",
            ready: false,
            connectionStatus: "CONNECTED",
            disconnectExpiresAtMs: null,
          },
        ],
        actions: [],
      }),
    );

    expect(
      await screen.findByText(/could not remove the former host invitation/i),
    ).toBeVisible();
    expect(localStorage.getItem("mahjong.room.room-a.session")).toBeNull();
  });

  it("renders disabled reasons as accessible visible text", () => {
    openHostLobby(
      roomView({
        actions: [
          {
            actionId: "opaque-disabled-start",
            label: "Start Match",
            enabled: false,
            tone: "primary",
            disabledReason: "All four players must be ready.",
            presentationSlot: "roomActions",
          },
        ],
      }),
    );

    const action = screen.getByRole("button", { name: "Start Match" });
    const reason = screen.getByText("All four players must be ready.");
    expect(action).toBeDisabled();
    expect(action).toHaveAttribute("aria-describedby", reason.id);
    expect(reason).toBeVisible();
  });

  it("submits opaque actions with a UUID and stores rotated invitations", async () => {
    const updated = roomView({ revision: 8 });
    vi.mocked(submitCommand).mockResolvedValue({
      type: "view",
      view: updated,
      inviteToken: "invite-rotated",
    });
    openHostLobby();

    fireEvent.click(
      screen.getByRole("button", { name: "Copy invitation link" }),
    );
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "http://localhost:3000/rooms/room-a#invite=invite-original",
      ),
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Create New Invitation Link" }),
    );
    await waitFor(() =>
      expect(submitCommand).toHaveBeenCalledWith("room-a", "host-secret", {
        commandId: "00000000-0000-4000-8000-000000000001",
        expectedRevision: 7,
        actionId: "opaque-rotate-id",
      }),
    );
    expect(loadRoomSession("room-a")?.inviteToken).toBe("invite-rotated");
    expect(screen.getByText("Revision 8", { exact: false })).toBeVisible();
  });

  it("refetches a conflict and ignores a later stale socket revision", async () => {
    vi.mocked(submitCommand).mockRejectedValue(
      new ApiError(409, "REVISION_CONFLICT", "Room changed", 9),
    );
    vi.mocked(getRoom).mockResolvedValue(roomView({ revision: 9 }));
    openHostLobby();

    fireEvent.click(screen.getByRole("button", { name: "Ready" }));
    expect(
      await screen.findByText("The room changed first. Your view has been refreshed."),
    ).toBeVisible();
    expect(screen.getByText("Revision 9", { exact: false })).toBeVisible();

    emitSocketView(roomView({ revision: 8 }));
    expect(screen.getByText("Revision 9", { exact: false })).toBeVisible();
  });

  it("does not regress presence when an older equal-revision view arrives", () => {
    const disconnected = viewWithDisconnectedMember({ presenceVersion: 3 });
    openHostLobby(disconnected);
    expect(screen.getByText("Disconnected")).toBeVisible();

    emitSocketView({
      ...disconnected,
      presenceVersion: 2,
      players: disconnected.players.map((player) =>
        player.playerId === "player-member"
          ? {
              ...player,
              connectionStatus: "CONNECTED" as const,
              disconnectExpiresAtMs: null,
            }
          : player,
      ),
    });

    expect(screen.getByText("Disconnected")).toBeVisible();
    expect(screen.getByText("Removing in 5:00")).toBeVisible();

    emitSocketView({
      ...disconnected,
      serverTimeMs: disconnected.serverTimeMs - 1_000,
    });
    expect(screen.queryByText("Removing in 5:01")).not.toBeInTheDocument();
    expect(screen.getByText("Removing in 5:00")).toBeVisible();
  });

  it("disables only the in-flight descriptor and retries with the same UUID", async () => {
    vi.mocked(submitCommand)
      .mockRejectedValueOnce(new TypeError("Connection reset"))
      .mockResolvedValueOnce({
        type: "view",
        view: roomView({ revision: 8 }),
      });
    openHostLobby();

    fireEvent.click(screen.getByRole("button", { name: "Ready" }));
    expect(await screen.findByRole("button", { name: "Retry safely" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Create New Invitation Link" }),
    ).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Retry safely" }));
    await waitFor(() => expect(submitCommand).toHaveBeenCalledTimes(2));
    expect(vi.mocked(submitCommand).mock.calls[1][2]).toEqual(
      vi.mocked(submitCommand).mock.calls[0][2],
    );
    expect(await screen.findByText("Revision 8", { exact: false })).toBeVisible();
  });

  it("retries an ambiguous gateway failure with the same UUID", async () => {
    vi.mocked(submitCommand)
      .mockRejectedValueOnce(
        new ApiError(503, "UPSTREAM_UNAVAILABLE", "Please try again"),
      )
      .mockResolvedValueOnce({
        type: "view",
        view: roomView({ revision: 8 }),
      });
    openHostLobby();

    fireEvent.click(screen.getByRole("button", { name: "Ready" }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry safely" }));

    await waitFor(() => expect(submitCommand).toHaveBeenCalledTimes(2));
    expect(vi.mocked(submitCommand).mock.calls[1][2]).toEqual(
      vi.mocked(submitCommand).mock.calls[0][2],
    );
  });

  it("clears credentials for an explicit session end", async () => {
    vi.mocked(submitCommand).mockResolvedValue({
      type: "sessionEnded",
      revision: 8,
    });
    openHostLobby();

    fireEvent.click(screen.getByRole("button", { name: "Ready" }));

    await waitFor(() => expect(location.pathname).toBe("/"));
    expect(loadRoomSession("room-a")).toBeNull();
    expect(
      screen.queryByRole("heading", { name: "Rejoin a room" }),
    ).not.toBeInTheDocument();
  });

  it("clears credentials on 401 revocation", async () => {
    vi.mocked(submitCommand).mockRejectedValue(
      new ApiError(401, "PLAYER_REVOKED", "This player was removed"),
    );
    openHostLobby();

    fireEvent.click(screen.getByRole("button", { name: "Ready" }));

    expect(
      await screen.findByRole("heading", {
        name: "This room session is unavailable",
      }),
    ).toBeVisible();
    expect(loadRoomSession("room-a")).toBeNull();
  });

  it("keeps valid credentials and displays a 403 role failure", async () => {
    vi.mocked(submitCommand).mockRejectedValue(
      new ApiError(403, "HOST_REQUIRED", "Only the host can do that"),
    );
    openHostLobby();

    fireEvent.click(screen.getByRole("button", { name: "Ready" }));

    expect(await screen.findByText("Only the host can do that")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Room lobby" })).toBeVisible();
    expect(loadRoomSession("room-a")?.playerToken).toBe("host-secret");
    expect(screen.getByRole("button", { name: "Ready" })).toBeEnabled();
  });

  it("shows a no-game-yet placeholder for PENDING_SETUP", () => {
    openHostLobby(
      roomView({
        status: "IN_MATCH",
        game: {
          status: "PENDING_SETUP",
          prevailingWind: "EAST",
          dealerSeatId: null,
          phase: null,
          liveWallTileCount: 0,
          reserveWallTileCount: 0,
          discards: [],
          balances: [],
          result: null,
          matchResult: null,
        },
      }),
    );
    expect(
      screen.getByRole("heading", {
        name: "Match started; gameplay arrives in Milestone 3",
      }),
    ).toBeVisible();
    expect(screen.queryByText("Copy invitation link")).not.toBeInTheDocument();
  });
});
