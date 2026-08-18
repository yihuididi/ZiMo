import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearRoomSession,
  listStoredRooms,
  loadRoomSession,
  removeStoredInviteToken,
  saveRoomSession,
  updateStoredInviteToken,
} from "./session";

describe("room-scoped browser sessions", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("keeps separate persistent credentials for each room", () => {
    saveRoomSession({
      version: 1,
      roomId: "room-a",
      playerId: "player-a",
      playerToken: "secret-a",
    });
    saveRoomSession({
      version: 1,
      roomId: "room-b",
      playerId: "player-b",
      playerToken: "secret-b",
      inviteToken: "invite-b",
    });

    expect(localStorage.getItem("mahjong.room.room-a.session")).not.toBeNull();
    sessionStorage.clear();
    expect(loadRoomSession("room-a")?.playerToken).toBe("secret-a");
    expect(loadRoomSession("room-b")?.playerToken).toBe("secret-b");
    clearRoomSession("room-a");
    expect(loadRoomSession("room-a")).toBeNull();
    expect(loadRoomSession("room-b")?.inviteToken).toBe("invite-b");
  });

  it("migrates a valid legacy tab session after a successful persistent write", () => {
    sessionStorage.setItem(
      "mahjong.room.room-a.session",
      JSON.stringify({
        version: 1,
        roomId: "room-a",
        playerId: "player-a",
        playerToken: "secret-a",
      }),
    );

    expect(loadRoomSession("room-a")?.playerToken).toBe("secret-a");
    expect(localStorage.getItem("mahjong.room.room-a.session")).toContain(
      "secret-a",
    );
    expect(sessionStorage.getItem("mahjong.room.room-a.session")).toBeNull();
  });

  it("retains a valid legacy session when persistent migration is blocked", () => {
    sessionStorage.setItem(
      "mahjong.room.room-a.session",
      JSON.stringify({
        version: 1,
        roomId: "room-a",
        playerId: "player-a",
        playerToken: "secret-a",
      }),
    );
    vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(() => {
      throw new DOMException("Storage denied", "SecurityError");
    });

    expect(loadRoomSession("room-a")?.playerToken).toBe("secret-a");
    expect(localStorage.getItem("mahjong.room.room-a.session")).toBeNull();
    expect(sessionStorage.getItem("mahjong.room.room-a.session")).not.toBeNull();
  });

  it("lists only non-secret room references newest first", () => {
    localStorage.setItem(
      "mahjong.room.room-a.session",
      JSON.stringify({
        version: 1,
        roomId: "room-a",
        playerId: "player-a",
        playerToken: "secret-a",
        savedAtMs: 100,
      }),
    );
    sessionStorage.setItem(
      "mahjong.room.room-b.session",
      JSON.stringify({
        version: 1,
        roomId: "room-b",
        playerId: "player-b",
        playerToken: "secret-b",
        savedAtMs: 200,
      }),
    );

    const rooms = listStoredRooms();
    expect(rooms).toEqual([
      { roomId: "room-b", lastUsedAtMs: 200 },
      { roomId: "room-a", lastUsedAtMs: 100 },
    ]);
    expect(JSON.stringify(rooms)).not.toContain("secret");
    expect(sessionStorage.getItem("mahjong.room.room-b.session")).toBeNull();
  });

  it("persists a rotated invite only for the host session", () => {
    const session = {
      version: 1 as const,
      roomId: "room-a",
      playerId: "host",
      playerToken: "host-secret",
      inviteToken: "old-invite",
    };
    saveRoomSession(session);
    updateStoredInviteToken(session, "new-invite");
    expect(loadRoomSession("room-a")?.inviteToken).toBe("new-invite");
  });

  it("removes a former host's stored invitation capability", () => {
    const session = {
      version: 1 as const,
      roomId: "room-a",
      playerId: "former-host",
      playerToken: "player-secret",
      inviteToken: "invite-secret",
    };
    saveRoomSession(session);

    const removal = removeStoredInviteToken(session);

    expect(removal.storageStatus).toBe("updated");
    expect(removal.session.inviteToken).toBeUndefined();
    expect(loadRoomSession("room-a")).toEqual({
      version: 1,
      roomId: "room-a",
      playerId: "former-host",
      playerToken: "player-secret",
    });
  });

  it("clears saved access when storage cannot overwrite a former host invite", () => {
    const session = {
      version: 1 as const,
      roomId: "room-a",
      playerId: "former-host",
      playerToken: "player-secret",
      inviteToken: "invite-secret",
    };
    saveRoomSession(session);
    vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(() => {
      throw new DOMException("Storage denied", "SecurityError");
    });

    const removal = removeStoredInviteToken(session);

    expect(removal.storageStatus).toBe("cleared");
    expect(removal.session.inviteToken).toBeUndefined();
    expect(loadRoomSession("room-a")).toBeNull();
  });

  it("reports failure when a legacy invite copy cannot be removed", () => {
    const session = {
      version: 1 as const,
      roomId: "room-a",
      playerId: "former-host",
      playerToken: "player-secret",
      inviteToken: "invite-secret",
    };
    saveRoomSession(session);
    sessionStorage.setItem(
      "mahjong.room.room-a.session",
      JSON.stringify({ ...session, savedAtMs: 1 }),
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

    const removal = removeStoredInviteToken(session);

    expect(removal.storageStatus).toBe("failed");
    expect(removal.session.inviteToken).toBeUndefined();
    expect(localStorage.getItem("mahjong.room.room-a.session")).toBeNull();
    expect(sessionStorage.getItem("mahjong.room.room-a.session")).toContain(
      "invite-secret",
    );
  });

  it("rejects malformed or cross-room records", () => {
    localStorage.setItem(
      "mahjong.room.room-a.session",
      JSON.stringify({ version: 1, roomId: "other", playerToken: 3 }),
    );
    expect(loadRoomSession("room-a")).toBeNull();
    expect(localStorage.getItem("mahjong.room.room-a.session")).toBeNull();
  });

  it("clears persistent and legacy copies together", () => {
    const value = JSON.stringify({
      version: 1,
      roomId: "room-a",
      playerId: "player-a",
      playerToken: "secret-a",
    });
    localStorage.setItem("mahjong.room.room-a.session", value);
    sessionStorage.setItem("mahjong.room.room-a.session", value);

    expect(clearRoomSession("room-a")).toBe(true);
    expect(localStorage.getItem("mahjong.room.room-a.session")).toBeNull();
    expect(sessionStorage.getItem("mahjong.room.room-a.session")).toBeNull();
  });
});
