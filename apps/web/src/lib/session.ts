export interface RoomSession {
  version: 1;
  roomId: string;
  playerId: string;
  playerToken: string;
  inviteToken?: string;
}

export interface StoredRoomReference {
  roomId: string;
  lastUsedAtMs: number;
}

export interface InviteTokenRemoval {
  session: RoomSession;
  storageStatus: "updated" | "cleared" | "failed";
}

interface PersistedRoomSession extends RoomSession {
  savedAtMs: number;
}

const SESSION_PREFIX = "mahjong.room.";
const SESSION_SUFFIX = ".session";

const sessionKey = (roomId: string) =>
  `${SESSION_PREFIX}${roomId}${SESSION_SUFFIX}`;

function browserStorage(name: "localStorage" | "sessionStorage"): Storage | null {
  try {
    return window[name];
  } catch {
    return null;
  }
}

export class RoomSessionStorageError extends Error {
  constructor() {
    super(
      "This browser blocked persistent storage, so the new room credentials could not be retained. This room session is unrecoverable; enable browser storage before trying again.",
    );
    this.name = "RoomSessionStorageError";
  }
}

function roomIdFromKey(key: string | null): string | null {
  if (
    !key ||
    !key.startsWith(SESSION_PREFIX) ||
    !key.endsWith(SESSION_SUFFIX)
  ) {
    return null;
  }
  const roomId = key.slice(SESSION_PREFIX.length, -SESSION_SUFFIX.length);
  return roomId || null;
}

function removeFrom(storage: Storage | null, roomId: string): boolean {
  if (!storage) return false;
  try {
    storage.removeItem(sessionKey(roomId));
    return true;
  } catch {
    return false;
  }
}

function parsePersistedSession(
  value: string,
  expectedRoomId: string,
): PersistedRoomSession | null {
  try {
    const parsed = JSON.parse(value) as Partial<PersistedRoomSession>;
    if (
      parsed.version !== 1 ||
      parsed.roomId !== expectedRoomId ||
      typeof parsed.playerId !== "string" ||
      parsed.playerId.length === 0 ||
      typeof parsed.playerToken !== "string" ||
      parsed.playerToken.length === 0 ||
      (parsed.inviteToken !== undefined &&
        (typeof parsed.inviteToken !== "string" ||
          parsed.inviteToken.length === 0)) ||
      (parsed.savedAtMs !== undefined &&
        (!Number.isSafeInteger(parsed.savedAtMs) || parsed.savedAtMs < 0))
    ) {
      return null;
    }
    return {
      version: 1,
      roomId: parsed.roomId,
      playerId: parsed.playerId,
      playerToken: parsed.playerToken,
      ...(parsed.inviteToken === undefined
        ? {}
        : { inviteToken: parsed.inviteToken }),
      savedAtMs: parsed.savedAtMs ?? 0,
    };
  } catch {
    return null;
  }
}

function readFrom(
  storage: Storage | null,
  roomId: string,
): PersistedRoomSession | null {
  if (!storage) return null;
  try {
    const value = storage.getItem(sessionKey(roomId));
    if (value === null) return null;
    const parsed = parsePersistedSession(value, roomId);
    if (!parsed) storage.removeItem(sessionKey(roomId));
    return parsed;
  } catch {
    return null;
  }
}

function publicSession(session: PersistedRoomSession): RoomSession {
  return {
    version: 1,
    roomId: session.roomId,
    playerId: session.playerId,
    playerToken: session.playerToken,
    ...(session.inviteToken === undefined
      ? {}
      : { inviteToken: session.inviteToken }),
  };
}

function writePersistent(session: RoomSession, savedAtMs = Date.now()): void {
  const storage = browserStorage("localStorage");
  if (!storage) throw new DOMException("Storage unavailable", "SecurityError");
  storage.setItem(
    sessionKey(session.roomId),
    JSON.stringify({ ...session, savedAtMs }),
  );
}

function storedRoomIds(storage: Storage | null): string[] {
  if (!storage) return [];
  const roomIds: string[] = [];
  try {
    for (let index = 0; index < storage.length; index += 1) {
      const roomId = roomIdFromKey(storage.key(index));
      if (roomId) roomIds.push(roomId);
    }
  } catch {
    return [];
  }
  return roomIds;
}

export function loadRoomSession(roomId: string): RoomSession | null {
  const persistentStorage = browserStorage("localStorage");
  const legacyStorage = browserStorage("sessionStorage");
  const persistent = readFrom(persistentStorage, roomId);
  if (persistent) {
    removeFrom(legacyStorage, roomId);
    return publicSession(persistent);
  }

  const legacy = readFrom(legacyStorage, roomId);
  if (!legacy) return null;
  try {
    writePersistent(publicSession(legacy), legacy.savedAtMs || Date.now());
    removeFrom(legacyStorage, roomId);
  } catch {
    // Keep the legacy record so the already-open tab can still reconnect.
  }
  return publicSession(legacy);
}

export function listStoredRooms(): StoredRoomReference[] {
  const persistentStorage = browserStorage("localStorage");
  const legacyStorage = browserStorage("sessionStorage");
  const roomIds = new Set([
    ...storedRoomIds(persistentStorage),
    ...storedRoomIds(legacyStorage),
  ]);
  const rooms: StoredRoomReference[] = [];
  for (const roomId of roomIds) {
    if (!loadRoomSession(roomId)) continue;
    const stored =
      readFrom(persistentStorage, roomId) ?? readFrom(legacyStorage, roomId);
    if (stored) rooms.push({ roomId, lastUsedAtMs: stored.savedAtMs });
  }
  return rooms.sort(
    (left, right) =>
      right.lastUsedAtMs - left.lastUsedAtMs ||
      left.roomId.localeCompare(right.roomId),
  );
}

export function saveRoomSession(session: RoomSession): void {
  try {
    writePersistent(session);
    removeFrom(browserStorage("sessionStorage"), session.roomId);
  } catch {
    throw new RoomSessionStorageError();
  }
}

export function touchRoomSession(session: RoomSession): void {
  try {
    writePersistent(session);
    removeFrom(browserStorage("sessionStorage"), session.roomId);
  } catch {
    // Existing access remains usable even if refreshing its timestamp fails.
  }
}

export function clearRoomSession(roomId: string): boolean {
  const persistentCleared = removeFrom(browserStorage("localStorage"), roomId);
  const legacyCleared = removeFrom(browserStorage("sessionStorage"), roomId);
  return persistentCleared && legacyCleared;
}

export function updateStoredInviteToken(
  session: RoomSession,
  inviteToken: string,
): RoomSession {
  const updated = { ...session, inviteToken };
  saveRoomSession(updated);
  return updated;
}

export function removeStoredInviteToken(
  session: RoomSession,
): InviteTokenRemoval {
  const { inviteToken: _inviteToken, ...updated } = session;
  try {
    writePersistent(updated);
    if (removeFrom(browserStorage("sessionStorage"), session.roomId)) {
      return { session: updated, storageStatus: "updated" };
    }
  } catch {
    // Fall through to removing every saved copy.
  }
  // If either store cannot be safely updated, removing the whole saved
  // session is safer than retaining an invitation after host demotion.
  const cleared = clearRoomSession(session.roomId);
  return {
    session: updated,
    storageStatus: cleared ? "cleared" : "failed",
  };
}
