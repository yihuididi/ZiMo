import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { createTestHarness } from "wrangler";
import WebSocket from "ws";

const FRONTEND_ORIGIN = "http://localhost:5173";
const HOSTILE_ORIGIN = "https://hostile.example";
const ROOM_NAME = "milestone-1-reconstruction";
const SNAPSHOT_JSON = JSON.stringify({
  roomId: ROOM_NAME,
  stateSchemaVersion: 2,
  seats: [0, 1, 2, 3].map((slot) => ({
    seatId: `seat-${slot}`,
    slot,
  })),
  createdAtMs: 1_700_000_000_000,
  updatedAtMs: 1_700_000_000_000,
});

const harness = createTestHarness({
  workers: [
    {
      configPath: new URL("../wrangler.jsonc", import.meta.url),
      secrets: {
        SUPABASE_URL: "https://example.invalid",
        SUPABASE_PUBLISHABLE_KEY: "test-publishable-key",
        FRONTEND_ORIGIN,
      },
    },
    {
      configPath: new URL("../worker-runtime.wrangler.jsonc", import.meta.url),
      secrets: {
        SUPABASE_URL: "https://example.invalid",
        SUPABASE_PUBLISHABLE_KEY: "test-publishable-key",
        FRONTEND_ORIGIN,
      },
    },
    {
      configPath: new URL("./worker-probe.wrangler.jsonc", import.meta.url),
    },
  ],
});

let apiWorker;
let runtimeWorker;
let probe;
let harnessUrl;
let commandSequence = 0;
const openSockets = new Set();

beforeAll(async () => {
  ({ url: harnessUrl } = await harness.listen());
  apiWorker = harness.getWorker("mahjong-api");
  runtimeWorker = harness.getWorker("mahjong-api-runtime-test");
  probe = harness.getWorker("mahjong-api-probe");
});

afterEach(() => {
  for (const socket of openSockets) {
    socket.terminate();
  }
  openSockets.clear();
});

afterAll(async () => {
  await harness.close();
});

function nextCommandId(label = "command") {
  commandSequence += 1;
  void label;
  return crypto.randomUUID();
}

async function roomFetch(
  pathname,
  {
    method = "GET",
    playerToken,
    body,
    origin = FRONTEND_ORIGIN,
    headers = {},
  } = {},
) {
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (origin !== null) {
    requestHeaders.set("Origin", origin);
  }
  if (playerToken !== undefined) {
    requestHeaders.set("Authorization", `Bearer ${playerToken}`);
  }
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }

  const response = await harness.fetch(pathname, {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (pathname.startsWith("/rooms")) {
    expect(response.headers.get("cache-control")).toBe("no-store");
  }
  return response;
}

async function responseJson(response) {
  expect(response.headers.get("content-type")).toMatch(/application\/json/i);
  return response.json();
}

async function expectApiError(response, status, code) {
  expect(response.status).toBe(status);
  const payload = await responseJson(response);
  expect(payload).toEqual({
    error: {
      code: code ?? expect.any(String),
      message: expect.any(String),
      ...(payload.error?.currentRevision === undefined
        ? {}
        : { currentRevision: expect.any(Number) }),
    },
  });
  return payload.error;
}

function expectAllowedCors(response) {
  expect(response.headers.get("access-control-allow-origin")).toBe(
    FRONTEND_ORIGIN,
  );
  expect(response.headers.get("vary")).toMatch(/origin/i);
}

function expectActionCatalog(view) {
  expect(Array.isArray(view.actions)).toBe(true);
  for (const action of view.actions) {
    expect(action).toMatchObject({
      actionId: expect.any(String),
      label: expect.any(String),
      enabled: expect.any(Boolean),
    });
    expect(Object.keys(action).sort()).toEqual(
      [
        "actionId",
        "label",
        "enabled",
        "tone",
        "disabledReason",
        "presentationSlot",
      ].sort(),
    );
    expect([null, "primary", "neutral", "danger"]).toContain(action.tone);
    expect(["roomActions", "invitation"]).toContain(action.presentationSlot);
    expect(
      action.disabledReason === null || typeof action.disabledReason === "string",
    ).toBe(true);
    expect(action.actionId).toMatch(/^[0-9a-f]{64}$/);
  }
  expect(new Set(view.actions.map(({ actionId }) => actionId)).size).toBe(
    view.actions.length,
  );
}

function findAction(view, label) {
  expectActionCatalog(view);
  const action = view.actions.find(
    (candidate) => candidate.label === label && candidate.enabled,
  );
  expect(action, `expected enabled action ${JSON.stringify(label)}`).toBeDefined();
  return action;
}

function viewerIndependentRoster(view) {
  return view.seats.map(({ seatId, slot, occupant }) => ({
    seatId,
    slot,
    occupant:
      occupant === null
        ? null
        : {
            controllerType: occupant.controllerType,
            displayName: occupant.displayName,
            playerId: occupant.playerId,
            role: occupant.role,
            ready: occupant.ready,
          },
  }));
}

function playerConnection(view, playerId) {
  const player = view.players.find((candidate) => candidate.playerId === playerId);
  expect(player, `expected player ${JSON.stringify(playerId)}`).toBeDefined();
  return {
    status: player.connectionStatus,
    expiresAtMs: player.disconnectExpiresAtMs,
  };
}

function expectConnected(view, playerId) {
  expect(playerConnection(view, playerId)).toEqual({
    status: "CONNECTED",
    expiresAtMs: null,
  });
}

function expectDisconnected(view, playerId, { expiring = true } = {}) {
  const connection = playerConnection(view, playerId);
  expect(connection.status).toBe("DISCONNECTED");
  if (!expiring) {
    expect(connection.expiresAtMs).toBeNull();
    return connection;
  }
  expect(connection.expiresAtMs).toEqual(expect.any(Number));
  expect(connection.expiresAtMs - view.serverTimeMs).toBeGreaterThan(298_000);
  expect(connection.expiresAtMs - view.serverTimeMs).toBeLessThanOrEqual(300_000);
  return connection;
}

async function closeRoomSocket(client, code = 1000, reason = "test close") {
  if (client.socket.readyState === WebSocket.CLOSED) return;
  const closed = new Promise((resolve) => {
    const timeout = setTimeout(resolve, 3_000);
    client.socket.once("close", () => {
      clearTimeout(timeout);
      resolve();
    });
  });
  client.socket.close(code, reason);
  await closed;
  openSockets.delete(client.socket);
}

async function createRoom(displayName = "Host") {
  const response = await roomFetch("/rooms", {
    method: "POST",
    body: { displayName },
  });
  expect(response.status).toBe(201);
  expectAllowedCors(response);
  const created = await responseJson(response);
  expect(created).toEqual({
    roomId: expect.stringMatching(/^[0-9a-f]{64}$/),
    playerId: expect.any(String),
    playerToken: expect.any(String),
    inviteToken: expect.any(String),
    view: expect.any(Object),
  });
  expect(created.view).toMatchObject({
    apiVersion: "1",
    roomId: created.roomId,
    viewerPlayerId: created.playerId,
    revision: 0,
    presenceVersion: 1,
    rulesetId: "singapore",
    rulesetVersion: "0.1.0",
    stateSchemaVersion: 2,
    capabilities: [
      "multiplayerLobby",
      "roomEvents",
      "hibernatingWebSockets",
    ],
  });
  expectDisconnected(created.view, created.playerId);
  expectActionCatalog(created.view);
  expect(JSON.stringify(created.view)).not.toContain(created.playerToken);
  expect(JSON.stringify(created.view)).not.toContain(created.inviteToken);
  return created;
}

async function joinRoom(roomId, inviteToken, displayName) {
  const response = await roomFetch(`/rooms/${roomId}/join`, {
    method: "POST",
    body: { inviteToken, displayName },
  });
  expect(response.status).toBe(201);
  const joined = await responseJson(response);
  expect(joined).toEqual({
    roomId,
    playerId: expect.any(String),
    playerToken: expect.any(String),
    view: expect.any(Object),
  });
  expect(joined.view).toMatchObject({
    roomId,
    viewerPlayerId: joined.playerId,
    presenceVersion: expect.any(Number),
  });
  expectDisconnected(joined.view, joined.playerId);
  expectActionCatalog(joined.view);
  expect(JSON.stringify(joined.view)).not.toContain(joined.playerToken);
  expect(JSON.stringify(joined)).not.toContain(inviteToken);
  return joined;
}

async function getRoomView(roomId, playerToken) {
  const response = await roomFetch(`/rooms/${roomId}`, { playerToken });
  expect(response.status).toBe(200);
  const view = await responseJson(response);
  expectActionCatalog(view);
  return view;
}

async function submitAction(
  roomId,
  playerToken,
  view,
  label,
  { commandId = nextCommandId(label.toLowerCase().replaceAll(" ", "-")) } = {},
) {
  const action = findAction(view, label);
  const request = {
    commandId,
    expectedRevision: view.revision,
    actionId: action.actionId,
  };
  const response = await roomFetch(`/rooms/${roomId}/commands`, {
    method: "POST",
    playerToken,
    body: request,
  });
  expect(response.status).toBe(200);
  return { request, result: await responseJson(response) };
}

async function issueSocketTicket(roomId, playerToken) {
  const response = await roomFetch(`/rooms/${roomId}/socket-ticket`, {
    method: "POST",
    playerToken,
  });
  expect(response.status).toBe(200);
  const ticket = await responseJson(response);
  expect(ticket).toEqual({
    ticket: expect.any(String),
    expiresAtMs: expect.any(Number),
  });
  expect(ticket.expiresAtMs).toBeGreaterThan(Date.now() + 20_000);
  expect(ticket.expiresAtMs).toBeLessThan(Date.now() + 40_000);
  return ticket;
}

function roomWebSocketUrl(roomId, search = "") {
  const url = new URL(`/rooms/${roomId}/ws${search}`, harnessUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url;
}

function dispatchSocketMessage(client, data) {
  let payload;
  try {
    payload = JSON.parse(data.toString());
  } catch (error) {
    for (const waiter of client.waiters.splice(0)) {
      clearTimeout(waiter.timeout);
      waiter.reject(error);
    }
    return;
  }

  const waiterIndex = client.waiters.findIndex(({ predicate }) =>
    predicate(payload),
  );
  if (waiterIndex === -1) {
    client.messages.push(payload);
    return;
  }
  const [waiter] = client.waiters.splice(waiterIndex, 1);
  clearTimeout(waiter.timeout);
  waiter.resolve(payload);
}

function nextSocketMessage(client, predicate = () => true, timeoutMs = 8_000) {
  const bufferedIndex = client.messages.findIndex(predicate);
  if (bufferedIndex !== -1) {
    return Promise.resolve(client.messages.splice(bufferedIndex, 1)[0]);
  }
  return new Promise((resolve, reject) => {
    const waiter = { predicate, resolve, reject, timeout: undefined };
    waiter.timeout = setTimeout(() => {
      const index = client.waiters.indexOf(waiter);
      if (index !== -1) {
        client.waiters.splice(index, 1);
      }
      reject(new Error("timed out waiting for WebSocket message"));
    }, timeoutMs);
    client.waiters.push(waiter);
  });
}

function safeWebSocketProblem(rawBody) {
  try {
    const payload = JSON.parse(rawBody);
    const error = payload?.error;
    if (typeof error?.code !== "string" || typeof error?.message !== "string") {
      return JSON.stringify({ error: "invalid JSON problem" });
    }
    return JSON.stringify({
      error: {
        code: error.code,
        message: error.message,
        ...(typeof error.currentRevision === "number"
          ? { currentRevision: error.currentRevision }
          : {}),
      },
    });
  } catch {
    return JSON.stringify({ error: "non-JSON problem" });
  }
}

async function connectRoomSocket(
  roomId,
  ticket,
  { origin = FRONTEND_ORIGIN, search = "", protocols } = {},
) {
  const requestedProtocols = protocols ?? ["mahjong.v1", `ticket.${ticket}`];
  const socketOptions = { handshakeTimeout: 8_000 };
  if (origin !== null) {
    socketOptions.origin = origin;
  }
  const socket = new WebSocket(
    roomWebSocketUrl(roomId, search),
    requestedProtocols,
    socketOptions,
  );
  openSockets.add(socket);
  const client = { socket, messages: [], waiters: [], upgradeHeaders: null };
  socket.on("message", (data) => dispatchSocketMessage(client, data));
  socket.on("upgrade", (response) => {
    client.upgradeHeaders = response.headers;
  });

  await new Promise((resolve, reject) => {
    let settled = false;
    socket.once("open", () => {
      if (settled) return;
      settled = true;
      resolve();
    });
    socket.once("error", (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    });
    socket.once("unexpected-response", (_request, response) => {
      if (settled) return;
      settled = true;
      response.setEncoding("utf8");
      let rawBody = "";
      response.on("data", (chunk) => {
        if (rawBody.length < 4_096) {
          rawBody += chunk.slice(0, 4_096 - rawBody.length);
        }
      });
      response.on("end", () => {
        reject(
          new Error(
            `unexpected WebSocket status ${response.statusCode}: ${safeWebSocketProblem(rawBody)}`,
          ),
        );
      });
    });
  });

  expect(socket.protocol).toBe("mahjong.v1");
  expect(client.upgradeHeaders?.["cache-control"]).toBe("no-store");
  expect(socket.url).not.toContain(ticket);
  return client;
}

async function expectSocketRejected(
  roomId,
  status,
  { ticket, origin = FRONTEND_ORIGIN, search = "", protocols } = {},
) {
  const requestedProtocols =
    protocols ??
    (ticket === undefined
      ? ["mahjong.v1"]
      : ["mahjong.v1", `ticket.${ticket}`]);
  const socketOptions = { handshakeTimeout: 8_000 };
  if (origin !== null) {
    socketOptions.origin = origin;
  }
  const socket = new WebSocket(
    roomWebSocketUrl(roomId, search),
    requestedProtocols,
    socketOptions,
  );
  openSockets.add(socket);

  const result = await new Promise((resolve, reject) => {
    let settled = false;
    socket.once("open", () => {
      if (!settled) {
        settled = true;
        reject(new Error("WebSocket unexpectedly opened"));
      }
    });
    socket.once("unexpected-response", (_request, response) => {
      if (settled) return;
      settled = true;
      const rejected = {
        status: response.statusCode,
        headers: response.headers,
      };
      response.resume();
      socket.terminate();
      resolve(rejected);
    });
    socket.once("error", (error) => {
      if (!settled) {
        settled = true;
        reject(error);
      }
    });
  });

  expect(result.status).toBe(status);
  expect(result.headers["cache-control"]).toBe("no-store");
  return result;
}

async function initializeFoundationRoom(snapshotJson) {
  const response = await probe.fetch(
    `http://probe.invalid/initialize?room=${encodeURIComponent(ROOM_NAME)}`,
    { method: "POST", body: snapshotJson },
  );
  if (!response.ok) {
    throw new Error(`Room initialization failed: ${await response.text()}`);
  }
  return response.text();
}

async function loadFoundationRoom() {
  const response = await probe.fetch(
    `http://probe.invalid/load?room=${encodeURIComponent(ROOM_NAME)}`,
  );
  if (response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Room load failed: ${await response.text()}`);
  }
  return response.text();
}

async function testRpc(pathname, method = "GET") {
  const response = await probe.fetch(
    `http://probe.invalid${pathname}?room=${encodeURIComponent(ROOM_NAME)}`,
    { method },
  );
  if (!response.ok) {
    throw new Error(`Test RPC ${pathname} failed: ${await response.text()}`);
  }
  return response.json();
}

async function probeRoomRpc(roomName, pathname, body) {
  const response = await probe.fetch(
    `http://probe.invalid${pathname}?room=${encodeURIComponent(roomName)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new Error(`Room test RPC ${pathname} failed with ${response.status}`);
  }
  return response.json();
}

describe("Milestone 1 foundation remains compatible", () => {
  it("keeps the health surface while exposing only native room IDs", async () => {
    const response = await harness.fetch("/health");
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      service: "mahjong-api",
    });

    const roomResponse = await roomFetch(`/rooms/${ROOM_NAME}`, {
      playerToken: "A".repeat(43),
    });
    await expectApiError(roomResponse, 404);
  });

  it("reconstructs the schema-v2 canonical room after eviction", async () => {
    await expect(loadFoundationRoom()).resolves.toBeNull();

    const canonicalSnapshot = await initializeFoundationRoom(SNAPSHOT_JSON);
    expect(JSON.parse(canonicalSnapshot)).toMatchObject({
      roomId: ROOM_NAME,
      revision: 0,
      rulesetId: "singapore",
      rulesetVersion: "0.1.0",
      stateSchemaVersion: 2,
    });
    await expect(loadFoundationRoom()).resolves.toBe(canonicalSnapshot);

    await expect(testRpc("/test/tables")).resolves.toEqual([
      "_sql_schema_migrations",
      "events",
      "player_presence",
      "players",
      "processed_commands",
      "room_credentials",
      "room_presence",
      "room_state",
      "socket_tickets",
    ]);
    await expect(testRpc("/test/counts")).resolves.toEqual({
      _sql_schema_migrations: 3,
      events: 0,
      player_presence: 0,
      players: 0,
      processed_commands: 0,
      room_credentials: 0,
      room_presence: 1,
      room_state: 1,
      socket_tickets: 0,
    });

    await expect(testRpc("/test/seed-auxiliary", "POST")).resolves.toEqual({
      _sql_schema_migrations: 3,
      events: 1,
      player_presence: 0,
      players: 1,
      processed_commands: 1,
      room_credentials: 0,
      room_presence: 1,
      room_state: 1,
      socket_tickets: 1,
    });
    await expect(testRpc("/test/clear-auxiliary", "POST")).resolves.toEqual({
      _sql_schema_migrations: 3,
      events: 0,
      player_presence: 0,
      players: 0,
      processed_commands: 0,
      room_credentials: 0,
      room_presence: 1,
      room_state: 1,
      socket_tickets: 0,
    });

    await expect(
      runtimeWorker.listDurableObjectIds("GAME_ROOM"),
    ).resolves.toHaveLength(1);
    await runtimeWorker.evictDurableObject("GAME_ROOM", { name: ROOM_NAME });
    await expect(loadFoundationRoom()).resolves.toBe(canonicalSnapshot);
  });
});

describe("Milestone 2 room HTTP API", () => {
  it("enforces strict input, native IDs, no-store, and exact-origin CORS", async () => {
    const strictCreate = await roomFetch("/rooms", {
      method: "POST",
      body: { displayName: "Host", playerId: "forged" },
    });
    await expectApiError(strictCreate, 422);

    const created = await createRoom();

    const unauthenticated = await roomFetch(`/rooms/${created.roomId}`);
    await expectApiError(unauthenticated, 401);

    const invalidToken = await roomFetch(`/rooms/${created.roomId}`, {
      playerToken: "not-a-player-token",
    });
    await expectApiError(invalidToken, 401);

    const forgedTokenBeforeBody = await roomFetch(
      `/rooms/${created.roomId}/commands`,
      {
        method: "POST",
        playerToken: "A".repeat(43),
        body: { malformed: true },
      },
    );
    await expectApiError(forgedTokenBeforeBody, 401);

    const invalidRoom = await roomFetch("/rooms/not-a-native-object-id", {
      playerToken: created.playerToken,
    });
    await expectApiError(invalidRoom, 404);

    const preflight = await roomFetch("/rooms", {
      method: "OPTIONS",
      headers: {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
      },
    });
    expect(preflight.status).toBe(200);
    expectAllowedCors(preflight);
    expect(preflight.headers.get("access-control-allow-methods")).toMatch(/POST/);
    expect(preflight.headers.get("access-control-allow-headers")).toMatch(
      /authorization/i,
    );

    const hostilePreflight = await roomFetch("/rooms", {
      method: "OPTIONS",
      origin: HOSTILE_ORIGIN,
      headers: {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
      },
    });
    await expectApiError(hostilePreflight, 403, "originDenied");
    expect(hostilePreflight.headers.get("access-control-allow-origin")).toBeNull();

    const hostileOrigin = await roomFetch(`/rooms/${created.roomId}`, {
      playerToken: created.playerToken,
      origin: HOSTILE_ORIGIN,
    });
    expect(hostileOrigin.status).toBe(200);
    expect(hostileOrigin.headers.get("access-control-allow-origin")).toBeNull();

    const allowedOrigin = await roomFetch(`/rooms/${created.roomId}`, {
      playerToken: created.playerToken,
    });
    expect(allowedOrigin.status).toBe(200);
    expectAllowedCors(allowedOrigin);
  });

  it("creates, joins, rotates invitations, and returns token-scoped views", async () => {
    const created = await createRoom("  Host Player  ");

    const rejectedJoin = await roomFetch(`/rooms/${created.roomId}/join`, {
      method: "POST",
      body: { inviteToken: "A".repeat(43), displayName: "Member" },
    });
    await expectApiError(rejectedJoin, 403);

    const member = await joinRoom(
      created.roomId,
      created.inviteToken,
      "  Member Player  ",
    );
    expect(member.playerId).not.toBe(created.playerId);
    expect(member.playerToken).not.toBe(created.playerToken);

    const hostView = await getRoomView(created.roomId, created.playerToken);
    const memberView = await getRoomView(created.roomId, member.playerToken);
    expect(hostView.revision).toBe(memberView.revision);
    expect(hostView.viewerPlayerId).toBe(created.playerId);
    expect(memberView.viewerPlayerId).toBe(member.playerId);
    expect(findAction(hostView, "Create New Invitation Link")).toMatchObject({
      presentationSlot: "invitation",
    });
    expect(memberView.actions.map(({ label }) => label)).not.toContain(
      "Create New Invitation Link",
    );
    expect(memberView.actions.map(({ label }) => label)).not.toContain("Add Bot");

    const memberConfig = await roomFetch(`/rooms/${created.roomId}/config`, {
      method: "PATCH",
      playerToken: member.playerToken,
      body: {
        expectedRevision: memberView.revision,
        config: memberView.config,
      },
    });
    await expectApiError(memberConfig, 403);

    const rotated = await submitAction(
      created.roomId,
      created.playerToken,
      hostView,
      "Create New Invitation Link",
    );
    expect(rotated.result).toEqual({
      type: "view",
      view: expect.any(Object),
      inviteToken: expect.any(String),
    });
    expect(rotated.result.inviteToken).not.toBe(created.inviteToken);

    const rotateRetry = await roomFetch(`/rooms/${created.roomId}/commands`, {
      method: "POST",
      playerToken: created.playerToken,
      body: rotated.request,
    });
    expect(rotateRetry.status).toBe(200);
    await expect(rotateRetry.json()).resolves.toEqual(rotated.result);

    const eventsResponse = await roomFetch(`/rooms/${created.roomId}/events`, {
      playerToken: created.playerToken,
    });
    expect(eventsResponse.status).toBe(200);
    const serializedEvents = JSON.stringify(await responseJson(eventsResponse));
    for (const rawSecret of [
      created.playerToken,
      created.inviteToken,
      rotated.result.inviteToken,
      member.playerToken,
    ]) {
      expect(serializedEvents).not.toContain(rawSecret);
    }

    const oldInvite = await roomFetch(`/rooms/${created.roomId}/join`, {
      method: "POST",
      body: { inviteToken: created.inviteToken, displayName: "Late Member" },
    });
    await expectApiError(oldInvite, 403);

    const lateMember = await joinRoom(
      created.roomId,
      rotated.result.inviteToken,
      "Late Member",
    );
    expect(lateMember.view.seats.filter(({ occupant }) => occupant).length).toBe(3);

    const serializedViews = JSON.stringify([
      hostView,
      memberView,
      lateMember.view,
    ]);
    for (const secret of [
      created.playerToken,
      created.inviteToken,
      rotated.result.inviteToken,
      member.playerToken,
      lateMember.playerToken,
    ]) {
      expect(serializedViews).not.toContain(secret);
    }
  });

  it("enforces opaque actions, optimistic revisions, and command idempotency", async () => {
    const created = await createRoom();
    const ticket = await issueSocketTicket(created.roomId, created.playerToken);
    const client = await connectRoomSocket(created.roomId, ticket.ticket);
    await nextSocketMessage(client, ({ type }) => type === "roomView");
    const initial = await getRoomView(created.roomId, created.playerToken);
    const repeated = await getRoomView(created.roomId, created.playerToken);
    expect(repeated.actions).toEqual(initial.actions);

    const commandId = nextCommandId("ready-idempotent");
    const ready = await submitAction(
      created.roomId,
      created.playerToken,
      initial,
      "Ready",
      { commandId },
    );
    expect(ready.result).toEqual({ type: "view", view: expect.any(Object) });
    expect(ready.result.view.revision).toBe(initial.revision + 1);
    const initialActionIds = new Set(initial.actions.map(({ actionId }) => actionId));
    expect(
      ready.result.view.actions.every(
        ({ actionId }) => !initialActionIds.has(actionId),
      ),
    ).toBe(true);

    const retry = await roomFetch(`/rooms/${created.roomId}/commands`, {
      method: "POST",
      playerToken: created.playerToken,
      body: ready.request,
    });
    expect(retry.status).toBe(200);
    await expect(retry.json()).resolves.toEqual(ready.result);

    const commandReuse = await roomFetch(`/rooms/${created.roomId}/commands`, {
      method: "POST",
      playerToken: created.playerToken,
      body: { ...ready.request, actionId: "forged-action-id" },
    });
    await expectApiError(commandReuse, 409);

    const stale = await roomFetch(`/rooms/${created.roomId}/commands`, {
      method: "POST",
      playerToken: created.playerToken,
      body: {
        commandId: nextCommandId("stale"),
        expectedRevision: initial.revision,
        actionId: findAction(initial, "Ready").actionId,
      },
    });
    const staleError = await expectApiError(stale, 409);
    expect(staleError.currentRevision).toBe(ready.result.view.revision);

    const forged = await roomFetch(`/rooms/${created.roomId}/commands`, {
      method: "POST",
      playerToken: created.playerToken,
      body: {
        commandId: nextCommandId("forged-seat"),
        expectedRevision: ready.result.view.revision,
        actionId: findAction(ready.result.view, "Unready").actionId,
        playerId: "forged-player",
      },
    });
    await expectApiError(forged, 422);

    const invalidAction = await roomFetch(`/rooms/${created.roomId}/commands`, {
      method: "POST",
      playerToken: created.playerToken,
      body: {
        commandId: nextCommandId("invalid-action"),
        expectedRevision: ready.result.view.revision,
        actionId: "forged-action-id",
      },
    });
    await expectApiError(invalidAction, 409);

    const configNoOp = await roomFetch(`/rooms/${created.roomId}/config`, {
      method: "PATCH",
      playerToken: created.playerToken,
      body: {
        expectedRevision: ready.result.view.revision,
        config: ready.result.view.config,
      },
    });
    expect(configNoOp.status).toBe(200);
    await expect(configNoOp.json()).resolves.toMatchObject({
      type: "view",
      view: { revision: ready.result.view.revision },
    });

    const unknownConfig = await roomFetch(`/rooms/${created.roomId}/config`, {
      method: "PATCH",
      playerToken: created.playerToken,
      body: {
        expectedRevision: ready.result.view.revision,
        config: { ...ready.result.view.config, clientRuleAuthority: true },
      },
    });
    await expectApiError(unknownConfig, 422);

    const eventsResponse = await roomFetch(`/rooms/${created.roomId}/events`, {
      playerToken: created.playerToken,
    });
    expect(eventsResponse.status).toBe(200);
    const eventPage = await responseJson(eventsResponse);
    expect(eventPage).toEqual({
      events: expect.any(Array),
      nextSequence: expect.any(Number),
    });
    expect(eventPage.events.length).toBeGreaterThan(0);
    for (const event of eventPage.events) {
      expect(event).toEqual({
        publicSequence: expect.any(Number),
        revision: expect.any(Number),
        type: expect.any(String),
        payload: expect.any(Object),
        createdAtMs: expect.any(Number),
      });
    }
    expect(JSON.stringify(eventPage)).not.toContain(created.playerToken);
    expect(JSON.stringify(eventPage)).not.toContain(created.inviteToken);
  });

  it("rejects a disconnected solo host's pre-close start descriptor", async () => {
    const created = await createRoom("Offline Solo Host");
    const start = created.view.actions.find(
      ({ label }) => label === "Start Against Bots",
    );
    expect(start).toMatchObject({
      actionId: expect.any(String),
      enabled: false,
      disabledReason: "Reconnect before starting.",
    });
    const rejected = await roomFetch(`/rooms/${created.roomId}/commands`, {
      method: "POST",
      playerToken: created.playerToken,
      body: {
        commandId: nextCommandId("offline-start-against-bots"),
        expectedRevision: created.view.revision,
        actionId: start.actionId,
      },
    });
    await expectApiError(rejected, 409, "actionNotAvailable");
    const unchanged = await getRoomView(created.roomId, created.playerToken);
    expect(unchanged).toMatchObject({
      revision: created.view.revision,
      status: "WAITING_FOR_PLAYERS",
    });
    expectDisconnected(unchanged, created.playerId);
  });

  it("supports four humans, readiness, and a frozen match roster", async () => {
    const host = await createRoom("Host");
    const humans = [host];
    for (const name of ["South", "West", "North"]) {
      humans.push(await joinRoom(host.roomId, host.inviteToken, name));
    }

    const occupied = humans.at(-1).view.seats.filter(({ occupant }) => occupant);
    expect(occupied).toHaveLength(4);
    expect(occupied.map(({ slot }) => slot)).toEqual([0, 1, 2, 3]);
    expect(
      occupied.every(({ occupant }) => occupant.controllerType === "external"),
    ).toBe(true);

    for (const human of humans) {
      const ticket = await issueSocketTicket(host.roomId, human.playerToken);
      const client = await connectRoomSocket(host.roomId, ticket.ticket);
      await nextSocketMessage(client, ({ type }) => type === "roomView");
    }

    for (const human of humans) {
      const view = await getRoomView(host.roomId, human.playerToken);
      const ready = await submitAction(
        host.roomId,
        human.playerToken,
        view,
        "Ready",
      );
      expect(ready.result.type).toBe("view");
    }

    const readyHostView = await getRoomView(host.roomId, host.playerToken);
    expect(readyHostView.status).toBe("READY");
    expect(readyHostView.players.every(({ ready }) => ready)).toBe(true);
    const started = await submitAction(
      host.roomId,
      host.playerToken,
      readyHostView,
      "Start Match",
    );
    expect(started.result).toMatchObject({
      type: "view",
      view: {
        status: "IN_MATCH",
        game: { status: "PENDING_SETUP", dealerSeatId: null },
      },
    });

    const fifthJoin = await roomFetch(`/rooms/${host.roomId}/join`, {
      method: "POST",
      body: { inviteToken: host.inviteToken, displayName: "Fifth" },
    });
    await expectApiError(fifthJoin, 409);

    const frozen = await getRoomView(host.roomId, humans[1].playerToken);
    expect(frozen.players).toEqual(started.result.view.players);
    expect(viewerIndependentRoster(frozen)).toEqual(
      viewerIndependentRoster(started.result.view),
    );
    expect(frozen.actions.map(({ label }) => label)).not.toContain("Leave Room");
    expect(frozen.actions.map(({ label }) => label)).not.toContain("Add Bot");
  });

  it("invalidates readiness, transfers host, and revokes removed sessions", async () => {
    const host = await createRoom("Original Host");
    const first = await joinRoom(host.roomId, host.inviteToken, "First Member");
    const second = await joinRoom(host.roomId, host.inviteToken, "Second Member");

    for (const player of [host, first, second]) {
      const ticket = await issueSocketTicket(host.roomId, player.playerToken);
      const client = await connectRoomSocket(host.roomId, ticket.ticket);
      await nextSocketMessage(client, ({ type }) => type === "roomView");
    }

    for (const player of [host, first, second]) {
      const view = await getRoomView(host.roomId, player.playerToken);
      await submitAction(host.roomId, player.playerToken, view, "Ready");
    }

    const hostView = await getRoomView(host.roomId, host.playerToken);
    const botAdded = await submitAction(
      host.roomId,
      host.playerToken,
      hostView,
      "Add Bot",
    );
    expect(botAdded.result.type).toBe("view");
    expect(botAdded.result.view.players.every(({ ready }) => !ready)).toBe(true);

    const leavingView = await getRoomView(host.roomId, host.playerToken);
    const left = await submitAction(
      host.roomId,
      host.playerToken,
      leavingView,
      "Leave Room",
    );
    expect(left.result).toEqual({
      type: "sessionEnded",
      revision: leavingView.revision + 1,
    });
    const revokedHost = await roomFetch(`/rooms/${host.roomId}`, {
      playerToken: host.playerToken,
    });
    await expectApiError(revokedHost, 401);

    const transferred = await getRoomView(host.roomId, first.playerToken);
    expect(
      transferred.players.find(({ playerId }) => playerId === first.playerId)?.role,
    ).toBe("HOST");
    expect(findAction(transferred, "Create New Invitation Link")).toMatchObject({
      presentationSlot: "invitation",
    });

    const promotedRotation = await submitAction(
      host.roomId,
      first.playerToken,
      transferred,
      "Create New Invitation Link",
    );
    expect(promotedRotation.result).toMatchObject({
      type: "view",
      inviteToken: expect.any(String),
    });
    expect(JSON.stringify(promotedRotation.result.view)).not.toContain(
      promotedRotation.result.inviteToken,
    );

    const staleInvite = await roomFetch(`/rooms/${host.roomId}/join`, {
      method: "POST",
      body: { inviteToken: host.inviteToken, displayName: "Stale Invite" },
    });
    await expectApiError(staleInvite, 403);
    const replacement = await joinRoom(
      host.roomId,
      promotedRotation.result.inviteToken,
      "Replacement Member",
    );
    expect(replacement.view.viewerPlayerId).toBe(replacement.playerId);

    const afterReplacement = await getRoomView(host.roomId, first.playerToken);
    const secondName = afterReplacement.players.find(
      ({ playerId }) => playerId === second.playerId,
    ).displayName;
    const removed = await submitAction(
      host.roomId,
      first.playerToken,
      afterReplacement,
      `Remove Player ${secondName}`,
    );
    expect(removed.result.type).toBe("view");
    const revokedMember = await roomFetch(`/rooms/${host.roomId}`, {
      playerToken: second.playerToken,
    });
    await expectApiError(revokedMember, 401);
  });

  it("starts against bots atomically and reconstructs solely from durable state", async () => {
    const host = await createRoom("Solo Host");
    const ticket = await issueSocketTicket(host.roomId, host.playerToken);
    const client = await connectRoomSocket(host.roomId, ticket.ticket);
    await nextSocketMessage(client, ({ type }) => type === "roomView");
    const initial = await getRoomView(host.roomId, host.playerToken);
    const started = await submitAction(
      host.roomId,
      host.playerToken,
      initial,
      "Start Against Bots",
    );
    expect(started.result.type).toBe("view");
    expect(started.result.view.status).toBe("IN_MATCH");
    expect(started.result.view.game).toMatchObject({
      status: "PENDING_SETUP",
      dealerSeatId: null,
    });
    expect(started.result.view.seats.filter(({ occupant }) => occupant)).toHaveLength(
      4,
    );
    expect(
      started.result.view.seats.filter(
        ({ occupant }) => occupant?.controllerType === "automated",
      ),
    ).toHaveLength(3);

    await apiWorker.evictDurableObject("GAME_ROOM", { id: host.roomId });
    const reconstructed = await getRoomView(host.roomId, host.playerToken);
    expect(reconstructed).toMatchObject({
      roomId: host.roomId,
      revision: started.result.view.revision,
      status: "IN_MATCH",
      config: started.result.view.config,
      players: started.result.view.players,
      seats: started.result.view.seats,
    });

    const lateJoin = await roomFetch(`/rooms/${host.roomId}/join`, {
      method: "POST",
      body: { inviteToken: host.inviteToken, displayName: "Too Late" },
    });
    await expectApiError(lateJoin, 409);
  });
});

describe("Milestone 2 hibernating WebSockets", () => {
  it("uses origin-checked, 30-second, single-use ticket subprotocols", async () => {
    const host = await createRoom("Socket Host");
    const firstTicket = await issueSocketTicket(host.roomId, host.playerToken);

    await expectSocketRejected(host.roomId, 403, {
      ticket: firstTicket.ticket,
      origin: null,
    });
    await expectSocketRejected(host.roomId, 403, {
      ticket: firstTicket.ticket,
      origin: HOSTILE_ORIGIN,
    });

    const firstClient = await connectRoomSocket(host.roomId, firstTicket.ticket);
    await expect(
      nextSocketMessage(firstClient, ({ type }) => type === "roomView"),
    ).resolves.toMatchObject({
      type: "roomView",
      view: {
        roomId: host.roomId,
        viewerPlayerId: host.playerId,
      },
    });

    await expectSocketRejected(host.roomId, 401, {
      ticket: firstTicket.ticket,
    });

    const queryTicket = await issueSocketTicket(host.roomId, host.playerToken);
    await expectSocketRejected(host.roomId, 401, {
      search: `?ticket=${encodeURIComponent(queryTicket.ticket)}`,
      protocols: ["mahjong.v1"],
    });
    const queryTicketClient = await connectRoomSocket(
      host.roomId,
      queryTicket.ticket,
    );
    await expect(
      nextSocketMessage(queryTicketClient, ({ type }) => type === "roomView"),
    ).resolves.toMatchObject({ type: "roomView" });

    await expectSocketRejected(host.roomId, 401, {
      protocols: ["mahjong.v1"],
    });

    const serializedLogs = JSON.stringify(harness.getLogs());
    for (const secret of [
      host.playerToken,
      host.inviteToken,
      firstTicket.ticket,
      queryTicket.ticket,
    ]) {
      expect(serializedLogs).not.toContain(secret);
    }
  });

  it("broadcasts individualized views to multiple connections across eviction", async () => {
    const host = await createRoom("Broadcast Host");
    const member = await joinRoom(host.roomId, host.inviteToken, "Broadcast Member");
    const [hostTicketOne, hostTicketTwo, memberTicket] = await Promise.all([
      issueSocketTicket(host.roomId, host.playerToken),
      issueSocketTicket(host.roomId, host.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
    ]);
    // Establish the current host first; a connected member is now eligible for
    // immediate host transfer while the previous host is still offline.
    const hostClientOne = await connectRoomSocket(
      host.roomId,
      hostTicketOne.ticket,
    );
    const [hostClientTwo, memberClient] = await Promise.all([
      connectRoomSocket(host.roomId, hostTicketTwo.ticket),
      connectRoomSocket(host.roomId, memberTicket.ticket),
    ]);

    for (const [client, playerId] of [
      [hostClientOne, host.playerId],
      [hostClientTwo, host.playerId],
      [memberClient, member.playerId],
    ]) {
      const initial = await nextSocketMessage(
        client,
        ({ type }) => type === "roomView",
      );
      expect(initial).toMatchObject({
        type: "roomView",
        view: { roomId: host.roomId, viewerPlayerId: playerId },
      });
    }

    const hostView = await getRoomView(host.roomId, host.playerToken);
    const ready = await submitAction(
      host.roomId,
      host.playerToken,
      hostView,
      "Ready",
    );
    for (const [client, playerId] of [
      [hostClientOne, host.playerId],
      [hostClientTwo, host.playerId],
      [memberClient, member.playerId],
    ]) {
      const broadcast = await nextSocketMessage(
        client,
        ({ type, view }) =>
          type === "roomView" && view.revision === ready.result.view.revision,
      );
      expect(broadcast.view.viewerPlayerId).toBe(playerId);
      expectActionCatalog(broadcast.view);
      if (playerId === host.playerId) {
        expect(findAction(broadcast.view, "Create New Invitation Link")).toMatchObject({
          presentationSlot: "invitation",
        });
      } else {
        expect(broadcast.view.actions.map(({ label }) => label)).not.toContain(
          "Create New Invitation Link",
        );
      }
    }

    await apiWorker.evictDurableObject("GAME_ROOM", {
      id: host.roomId,
      webSockets: "hibernate",
    });

    const afterEviction = await getRoomView(host.roomId, host.playerToken);
    const unready = await submitAction(
      host.roomId,
      host.playerToken,
      afterEviction,
      "Unready",
    );
    for (const client of [hostClientOne, hostClientTwo, memberClient]) {
      await expect(
        nextSocketMessage(
          client,
          ({ type, view }) =>
            type === "roomView" && view.revision === unready.result.view.revision,
        ),
      ).resolves.toMatchObject({ type: "roomView" });
      expect(client.socket.readyState).toBe(WebSocket.OPEN);
    }

    const reconnectTicket = await issueSocketTicket(host.roomId, host.playerToken);
    const reconnected = await connectRoomSocket(host.roomId, reconnectTicket.ticket);
    await expect(
      nextSocketMessage(reconnected, ({ type }) => type === "roomView"),
    ).resolves.toMatchObject({
      type: "roomView",
      view: {
        viewerPlayerId: host.playerId,
        revision: unready.result.view.revision,
      },
    });
  });

  it("atomically disconnects and unreadies a ready member", async () => {
    const host = await createRoom("Ready Disconnect Host");
    const member = await joinRoom(
      host.roomId,
      host.inviteToken,
      "Ready Disconnect Member",
    );
    const [hostTicket, memberTicket] = await Promise.all([
      issueSocketTicket(host.roomId, host.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
    ]);
    const hostClient = await connectRoomSocket(host.roomId, hostTicket.ticket);
    await nextSocketMessage(hostClient, ({ type }) => type === "roomView");
    const memberClient = await connectRoomSocket(
      host.roomId,
      memberTicket.ticket,
    );
    await nextSocketMessage(memberClient, ({ type }) => type === "roomView");

    const memberView = await getRoomView(host.roomId, member.playerToken);
    const ready = await submitAction(
      host.roomId,
      member.playerToken,
      memberView,
      "Ready",
    );
    await nextSocketMessage(
      hostClient,
      ({ type, view }) =>
        type === "roomView" && view.revision === ready.result.view.revision,
    );
    const eventsBeforeDisconnect = await roomFetch(
      `/rooms/${host.roomId}/events`,
      { playerToken: host.playerToken },
    );
    expect(eventsBeforeDisconnect.status).toBe(200);
    const beforePage = await responseJson(eventsBeforeDisconnect);

    const atomicFramePromise = nextSocketMessage(
      hostClient,
      ({ type, view }) => {
        const projected = view?.players?.find(
          ({ playerId }) => playerId === member.playerId,
        );
        return (
          type === "roomView" &&
          view.revision === ready.result.view.revision + 1 &&
          projected?.connectionStatus === "DISCONNECTED" &&
          projected.ready === false
        );
      },
    );
    await closeRoomSocket(memberClient);
    const atomicFrame = await atomicFramePromise;
    expect(atomicFrame.view.presenceVersion).toBeGreaterThan(
      ready.result.view.presenceVersion,
    );
    expectDisconnected(atomicFrame.view, member.playerId);
    expect(
      atomicFrame.view.players.find(
        ({ playerId }) => playerId === member.playerId,
      )?.ready,
    ).toBe(false);

    const disconnectEvents = await roomFetch(
      `/rooms/${host.roomId}/events?afterSequence=${beforePage.nextSequence}`,
      { playerToken: host.playerToken },
    );
    expect(disconnectEvents.status).toBe(200);
    const eventPage = await responseJson(disconnectEvents);
    expect(eventPage.events).toEqual([
      expect.objectContaining({
        revision: atomicFrame.view.revision,
        type: "playerReadinessChanged",
        payload: expect.objectContaining({
          playerId: member.playerId,
          ready: false,
        }),
      }),
    ]);
  });

  it("immediately transfers host to an already-connected member", async () => {
    const host = await createRoom("Disconnecting Host");
    const member = await joinRoom(
      host.roomId,
      host.inviteToken,
      "Connected Successor",
    );
    const [hostTicket, memberTicket] = await Promise.all([
      issueSocketTicket(host.roomId, host.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
    ]);
    const hostClient = await connectRoomSocket(host.roomId, hostTicket.ticket);
    await nextSocketMessage(hostClient, ({ type }) => type === "roomView");
    const memberClient = await connectRoomSocket(
      host.roomId,
      memberTicket.ticket,
    );
    await nextSocketMessage(memberClient, ({ type }) => type === "roomView");
    const baseline = await getRoomView(host.roomId, member.playerToken);

    const transferFramePromise = nextSocketMessage(
      memberClient,
      ({ type, view }) =>
        type === "roomView" &&
        view.revision === baseline.revision + 1 &&
        view.players.find(({ playerId }) => playerId === member.playerId)?.role ===
          "HOST",
    );
    await closeRoomSocket(hostClient);
    const transferred = await transferFramePromise;
    expectDisconnected(transferred.view, host.playerId);
    expect(transferred.view.players).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          playerId: host.playerId,
          role: "MEMBER",
        }),
        expect.objectContaining({
          playerId: member.playerId,
          role: "HOST",
          connectionStatus: "CONNECTED",
        }),
      ]),
    );
    expect(transferred.view.seats.filter(({ occupant }) => occupant)).toHaveLength(2);

    const retainedSession = await getRoomView(host.roomId, host.playerToken);
    expect(
      retainedSession.players.find(({ playerId }) => playerId === host.playerId)
        ?.role,
    ).toBe("MEMBER");
    const reconnectTicket = await issueSocketTicket(
      host.roomId,
      host.playerToken,
    );
    const reconnectedHost = await connectRoomSocket(
      host.roomId,
      reconnectTicket.ticket,
    );
    const reconnectedFrame = await nextSocketMessage(
      reconnectedHost,
      ({ type, view }) =>
        type === "roomView" &&
        playerConnection(view, host.playerId).status === "CONNECTED",
    );
    expect(
      reconnectedFrame.view.players.find(
        ({ playerId }) => playerId === host.playerId,
      )?.role,
    ).toBe("MEMBER");
  });

  it("retains an offline host until a successor actually connects", async () => {
    const host = await createRoom("Deferred Host");
    const member = await joinRoom(
      host.roomId,
      host.inviteToken,
      "Deferred Successor",
    );
    const hostTicket = await issueSocketTicket(host.roomId, host.playerToken);
    const hostClient = await connectRoomSocket(host.roomId, hostTicket.ticket);
    await nextSocketMessage(hostClient, ({ type }) => type === "roomView");
    const baseline = await getRoomView(host.roomId, member.playerToken);

    await closeRoomSocket(hostClient);
    const withoutSuccessor = await getRoomView(host.roomId, member.playerToken);
    expect(withoutSuccessor.revision).toBe(baseline.revision);
    expectDisconnected(withoutSuccessor, host.playerId);
    expect(
      withoutSuccessor.players.find(({ playerId }) => playerId === host.playerId)
        ?.role,
    ).toBe("HOST");

    const memberTicket = await issueSocketTicket(
      host.roomId,
      member.playerToken,
    );
    const connectedMember = await connectRoomSocket(
      host.roomId,
      memberTicket.ticket,
    );
    const transferFrame = await nextSocketMessage(
      connectedMember,
      ({ type, view }) =>
        type === "roomView" &&
        view.revision === withoutSuccessor.revision + 1,
    );
    expectConnected(transferFrame.view, member.playerId);
    expectDisconnected(transferFrame.view, host.playerId);
    expect(transferFrame.view.players).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ playerId: host.playerId, role: "MEMBER" }),
        expect.objectContaining({ playerId: member.playerId, role: "HOST" }),
      ]),
    );
  });

  it("projects a durable five-minute disconnect deadline and cancels it on reconnect", async () => {
    const host = await createRoom("Presence Host");
    const member = await joinRoom(
      host.roomId,
      host.inviteToken,
      "Presence Member",
    );
    const [hostTicket, memberTicket] = await Promise.all([
      issueSocketTicket(host.roomId, host.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
    ]);
    const hostClient = await connectRoomSocket(host.roomId, hostTicket.ticket);
    const memberClient = await connectRoomSocket(
      host.roomId,
      memberTicket.ticket,
    );
    await nextSocketMessage(hostClient, ({ type }) => type === "roomView");
    await nextSocketMessage(memberClient, ({ type }) => type === "roomView");

    const connected = await getRoomView(host.roomId, host.playerToken);
    const memberBeforeDisconnect = await getRoomView(
      host.roomId,
      member.playerToken,
    );
    const preCloseReadyAction = findAction(memberBeforeDisconnect, "Ready");
    expectConnected(connected, member.playerId);
    const roomRevision = connected.revision;
    const connectedPresenceVersion = connected.presenceVersion;

    const disconnectedFramePromise = nextSocketMessage(
      hostClient,
      ({ type, view }) =>
        type === "roomView" &&
        playerConnection(view, member.playerId).status === "DISCONNECTED",
    );
    await closeRoomSocket(memberClient);
    const disconnectedFrame = await disconnectedFramePromise;
    expect(disconnectedFrame.view.revision).toBe(roomRevision);
    expect(disconnectedFrame.view.presenceVersion).toBeGreaterThan(
      connectedPresenceVersion,
    );
    const disconnected = expectDisconnected(
      disconnectedFrame.view,
      member.playerId,
    );

    const offlineReady = await roomFetch(`/rooms/${host.roomId}/commands`, {
      method: "POST",
      playerToken: member.playerToken,
      body: {
        commandId: nextCommandId("offline-ready"),
        expectedRevision: roomRevision,
        actionId: preCloseReadyAction.actionId,
      },
    });
    await expectApiError(offlineReady, 409, "actionNotAvailable");
    const unchangedOfflineView = await getRoomView(
      host.roomId,
      member.playerToken,
    );
    expect(unchangedOfflineView.revision).toBe(roomRevision);
    expect(
      unchangedOfflineView.players.find(
        ({ playerId }) => playerId === member.playerId,
      )?.ready,
    ).toBe(false);
    expect(
      unchangedOfflineView.actions.find(({ label }) => label === "Ready"),
    ).toMatchObject({
      actionId: preCloseReadyAction.actionId,
      enabled: false,
      disabledReason: "Reconnect before getting ready.",
    });
    expectDisconnected(unchangedOfflineView, member.playerId);

    await apiWorker.evictDurableObject("GAME_ROOM", {
      id: host.roomId,
      webSockets: "hibernate",
    });
    const reconstructed = await getRoomView(host.roomId, host.playerToken);
    expect(reconstructed.revision).toBe(roomRevision);
    expect(reconstructed.presenceVersion).toBe(
      disconnectedFrame.view.presenceVersion,
    );
    expect(playerConnection(reconstructed, member.playerId)).toEqual(
      disconnected,
    );
    expect(hostClient.socket.readyState).toBe(WebSocket.OPEN);

    const reconnectTicket = await issueSocketTicket(
      host.roomId,
      member.playerToken,
    );
    const reconnectedClient = await connectRoomSocket(
      host.roomId,
      reconnectTicket.ticket,
    );
    const [hostReconnectFrame, memberReconnectFrame] = await Promise.all([
      nextSocketMessage(
        hostClient,
        ({ type, view }) =>
          type === "roomView" &&
          view.presenceVersion > disconnectedFrame.view.presenceVersion &&
          playerConnection(view, member.playerId).status === "CONNECTED",
      ),
      nextSocketMessage(
        reconnectedClient,
        ({ type, view }) =>
          type === "roomView" &&
          playerConnection(view, member.playerId).status === "CONNECTED",
      ),
    ]);
    expect(hostReconnectFrame.view.revision).toBe(roomRevision);
    expect(hostReconnectFrame.view.presenceVersion).toBeGreaterThan(
      disconnectedFrame.view.presenceVersion,
    );
    expectConnected(hostReconnectFrame.view, member.playerId);
    expect(memberReconnectFrame.view.presenceVersion).toBe(
      hostReconnectFrame.view.presenceVersion,
    );

    const restored = await getRoomView(host.roomId, member.playerToken);
    expect(restored.revision).toBe(roomRevision);
    expect(restored.presenceVersion).toBe(
      hostReconnectFrame.view.presenceVersion,
    );
    expectConnected(restored, member.playerId);
  });

  it("starts the grace period only after a player's last socket closes", async () => {
    const host = await createRoom("Multi-tab Host");
    const member = await joinRoom(
      host.roomId,
      host.inviteToken,
      "Multi-tab Member",
    );
    const [hostTicket, memberTicketOne, memberTicketTwo] = await Promise.all([
      issueSocketTicket(host.roomId, host.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
    ]);
    const hostClient = await connectRoomSocket(host.roomId, hostTicket.ticket);
    const [memberClientOne, memberClientTwo] = await Promise.all([
      connectRoomSocket(host.roomId, memberTicketOne.ticket),
      connectRoomSocket(host.roomId, memberTicketTwo.ticket),
    ]);
    for (const client of [hostClient, memberClientOne, memberClientTwo]) {
      await nextSocketMessage(client, ({ type }) => type === "roomView");
    }

    const baseline = await getRoomView(host.roomId, host.playerToken);
    expectConnected(baseline, member.playerId);
    await closeRoomSocket(memberClientOne);

    // Let the close callback complete, then serialize through the same object.
    await getRoomView(host.roomId, host.playerToken);
    const oneTabRemaining = await getRoomView(host.roomId, host.playerToken);
    expect(oneTabRemaining.presenceVersion).toBe(baseline.presenceVersion);
    expectConnected(oneTabRemaining, member.playerId);

    const disconnectedFramePromise = nextSocketMessage(
      hostClient,
      ({ type, view }) =>
        type === "roomView" &&
        view.presenceVersion > baseline.presenceVersion &&
        playerConnection(view, member.playerId).status === "DISCONNECTED",
    );
    await closeRoomSocket(memberClientTwo);
    const disconnectedFrame = await disconnectedFramePromise;
    expect(disconnectedFrame.view.revision).toBe(baseline.revision);
    expect(disconnectedFrame.view.presenceVersion).toBe(
      baseline.presenceVersion + 1,
    );
    expectDisconnected(disconnectedFrame.view, member.playerId);
  });

  it("rejects tickets and bearer tokens after player removal", async () => {
    const host = await createRoom("Revoking Host");
    const member = await joinRoom(host.roomId, host.inviteToken, "Revoked Member");
    const [hostTicket, liveTicket, unusedTicket] = await Promise.all([
      issueSocketTicket(host.roomId, host.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
      issueSocketTicket(host.roomId, member.playerToken),
    ]);
    const hostClient = await connectRoomSocket(host.roomId, hostTicket.ticket);
    await expect(
      nextSocketMessage(hostClient, ({ type }) => type === "roomView"),
    ).resolves.toMatchObject({
      type: "roomView",
      view: { viewerPlayerId: host.playerId },
    });
    const memberClient = await connectRoomSocket(host.roomId, liveTicket.ticket);
    await expect(
      nextSocketMessage(memberClient, ({ type }) => type === "roomView"),
    ).resolves.toMatchObject({
      type: "roomView",
      view: { viewerPlayerId: member.playerId },
    });
    const hostView = await getRoomView(host.roomId, host.playerToken);
    const memberName = hostView.players.find(
      ({ playerId }) => playerId === member.playerId,
    ).displayName;
    await submitAction(
      host.roomId,
      host.playerToken,
      hostView,
      `Remove Player ${memberName}`,
    );
    // Workerd's harness leaves the Node-side proxy in CLOSING after the DO's
    // server socket is already closed; observing a non-OPEN state proves the
    // revocation close frame was initiated without relying on proxy teardown.
    expect([WebSocket.CLOSING, WebSocket.CLOSED]).toContain(
      memberClient.socket.readyState,
    );

    const revokedBearer = await roomFetch(`/rooms/${host.roomId}`, {
      playerToken: member.playerToken,
    });
    await expectApiError(revokedBearer, 401);
    await expectSocketRejected(host.roomId, 401, {
      ticket: unusedTicket.ticket,
    });
  });
});

describe("Milestone 2 durable presence alarms", () => {
  it("reconciles a hibernated socket batch by durable join order", async () => {
    const roomName = `presence-reconcile-${crypto.randomUUID()}`;
    const createdEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/create",
      { displayName: "Offline Host" },
    );
    expect(createdEnvelope).toEqual({ ok: true, data: expect.any(Object) });
    const host = createdEnvelope.data;

    const firstEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/join",
      {
        inviteToken: host.inviteToken,
        displayName: "First Successor",
      },
    );
    expect(firstEnvelope).toEqual({ ok: true, data: expect.any(Object) });
    const first = firstEnvelope.data;

    const secondEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/join",
      {
        inviteToken: host.inviteToken,
        displayName: "Second Successor",
      },
    );
    expect(secondEnvelope).toEqual({ ok: true, data: expect.any(Object) });
    const second = secondEnvelope.data;
    expect(second.view.revision).toBe(2);
    const hostPresence = expectDisconnected(second.view, host.playerId);

    await runtimeWorker.evictDurableObject("GAME_ROOM", {
      name: roomName,
      webSockets: "hibernate",
    });

    // Deliberately report the later join first. The production batch
    // reconciler must choose its successor from durable join metadata rather
    // than callback or socket enumeration order.
    const reconciled = await probeRoomRpc(
      roomName,
      "/test/room/reconcile-hibernated",
      { connectedPlayerIds: [second.playerId, first.playerId] },
    );
    expect(reconciled).toMatchObject({
      changed: true,
      scheduledAlarmMs: hostPresence.expiresAtMs,
      view: {
        revision: 3,
        viewerPlayerId: second.playerId,
      },
    });
    expectDisconnected(reconciled.view, host.playerId);
    expectConnected(reconciled.view, first.playerId);
    expectConnected(reconciled.view, second.playerId);
    expect(reconciled.view.players).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ playerId: host.playerId, role: "MEMBER" }),
        expect.objectContaining({ playerId: first.playerId, role: "HOST" }),
        expect.objectContaining({ playerId: second.playerId, role: "MEMBER" }),
      ]),
    );

    const eventsEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/events",
      { playerToken: first.playerToken, afterSequence: 0 },
    );
    expect(eventsEnvelope).toEqual({ ok: true, data: expect.any(Object) });
    expect(eventsEnvelope.data.events).toContainEqual(
      expect.objectContaining({
        revision: 3,
        type: "hostTransferred",
        payload: {
          fromPlayerId: host.playerId,
          toPlayerId: first.playerId,
        },
      }),
    );

    const repeated = await probeRoomRpc(
      roomName,
      "/test/room/reconcile-hibernated",
      { connectedPlayerIds: [first.playerId, second.playerId] },
    );
    expect(repeated).toMatchObject({
      changed: false,
      scheduledAlarmMs: hostPresence.expiresAtMs,
      view: { revision: 3 },
    });
  });

  it("expires an offline host through the real alarm and keeps the next deadline", async () => {
    const roomName = `presence-alarm-${crypto.randomUUID()}`;
    const createdEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/create",
      { displayName: "Expiring Host" },
    );
    expect(createdEnvelope).toEqual({ ok: true, data: expect.any(Object) });
    const host = createdEnvelope.data;

    const joinedEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/join",
      {
        inviteToken: host.inviteToken,
        displayName: "Promoted Member",
      },
    );
    expect(joinedEnvelope).toEqual({ ok: true, data: expect.any(Object) });
    const member = joinedEnvelope.data;
    expect(member.view.revision).toBe(1);
    expectDisconnected(member.view, host.playerId);
    const memberPresence = expectDisconnected(member.view, member.playerId);

    const alarmResult = await probeRoomRpc(
      roomName,
      "/test/room/expire",
      { playerId: host.playerId },
    );
    expect(alarmResult).toEqual({
      nextPlayerId: member.playerId,
      nextPresenceDeadlineMs: memberPresence.expiresAtMs,
      scheduledAlarmMs: memberPresence.expiresAtMs,
    });

    const hostViewEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/view",
      { playerToken: host.playerToken },
    );
    expect(hostViewEnvelope).toMatchObject({
      ok: false,
      error: { code: "invalidPlayerToken", status: 401 },
    });

    const memberViewEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/view",
      { playerToken: member.playerToken },
    );
    expect(memberViewEnvelope).toEqual({
      ok: true,
      data: expect.any(Object),
    });
    const promotedView = memberViewEnvelope.data;
    expect(promotedView.revision).toBe(2);
    expect(promotedView.players).toEqual([
      expect.objectContaining({
        playerId: member.playerId,
        role: "HOST",
        connectionStatus: "DISCONNECTED",
        disconnectExpiresAtMs: memberPresence.expiresAtMs,
      }),
    ]);
    expect(promotedView.seats.find(({ slot }) => slot === 0)?.occupant).toBeNull();
    expect(
      promotedView.seats.find(({ slot }) => slot === 1)?.occupant?.playerId,
    ).toBe(member.playerId);

    const eventsEnvelope = await probeRoomRpc(
      roomName,
      "/test/room/events",
      { playerToken: member.playerToken, afterSequence: 0 },
    );
    expect(eventsEnvelope).toEqual({ ok: true, data: expect.any(Object) });
    const eventTypes = eventsEnvelope.data.events.map(({ type }) => type);
    expect(eventTypes).toContain("playerLeft");
    expect(eventTypes).toContain("hostTransferred");
    const serializedEvents = JSON.stringify(eventsEnvelope.data);
    for (const secret of [
      host.playerToken,
      host.inviteToken,
      member.playerToken,
    ]) {
      expect(serializedEvents).not.toContain(secret);
    }
  });
});
